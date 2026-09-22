"""A front door on the WebView2 DevTools port, so chromedriver will attach to it.

chromedriver checks the browser it is asked to attach to: it reads GET /json/version on
the debuggerAddress it was given and refuses anything whose "Browser" is not Chrome -
"unrecognized Chrome version: Edg/153.0.4234.48", with or without
--disable-build-check. WebView2 is that same Chromium underneath the Edge name, and it
answers every DevTools command chromedriver sends; only the name is in the way. This
listener stands in front of the real port: it answers /json/version itself with the
"Edg/<version>" rewritten to "Chrome/<version>" and passes every other request
through byte for byte.

What chromedriver 153 does with the door, as observed: GET /json/version and GET
/json/list come through it (the list on a connection it keeps alive and reuses), then
it opens its websocket straight to the real port, taking webSocketDebuggerUrl as given.
The relay carries the websocket too, for a chromedriver that resolves the path against
the debuggerAddress instead. Plain HTTP connections are kept alive and every request on
them is dispatched on its own: chromedriver pools the connection it fetched /json/list
on and would otherwise send a later /json/version down it, past the rewrite (its second
session in one process does exactly that).

The door speaks 127.0.0.1 only, on both sides. Chromium binds its DevTools server to
127.0.0.1, and on Windows a name such as localhost is tried on ::1 first, which costs
2 s per connection - on every session chromedriver creates and every /json/list it
fetches. So neither the listener nor the debuggerAddress ever carries a name.
"""
import ipaddress
import re
import select
import socket
import threading
import urllib.request

HOST = "127.0.0.1"
VERSION_PATH = b"/json/version"
BROWSER_NAME = re.compile(rb'("Browser":\s*")[^"/]*/')
CONTENT_LENGTH = re.compile(rb"\r\nContent-Length:[ \t]*(\d+)", re.I)
HOST_NAME = re.compile(rb"\r\nHost:[ \t]*(\[[^\]\r\n]*\]|[^:\r\n]*)", re.I)
# No system proxy may sit between the front door and the browser on this machine.
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def local_host(head):
    """Chromium answers /json only to a Host that is an IP literal or localhost (a guard
    against DNS rebinding); the door answers /json/version on the same terms."""
    match = HOST_NAME.search(head)
    if match is None:
        return True
    name = match.group(1).strip(b"[] ").decode("latin-1")
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        return name == "localhost" or name.endswith(".localhost")


def response_length(seen):
    """Bytes in a whole HTTP response once its head is in; None while the head is incomplete,
    infinity when the response has no Content-Length (then it ends when the browser hangs up)."""
    end = seen.find(b"\r\n\r\n")
    if end < 0:
        return None
    match = CONTENT_LENGTH.search(seen[:end + 2])
    return end + 4 + int(match.group(1)) if match else float("inf")


class FrontDoor:
    """A listener on a free local port that fronts the DevTools server on target_port."""

    def __init__(self, target_port):
        self.target_port = target_port
        self._listener = socket.socket()
        self._listener.bind((HOST, 0))
        self._listener.settimeout(0.2)   # so the accept loop notices stop() promptly
        self.port = self._listener.getsockname()[1]
        self.version_requests = 0
        self.relayed_requests = 0
        self.websocket_upgrades = 0
        self._stopping = threading.Event()
        self._lock = threading.Lock()
        self._sockets = set()
        self._threads = []

    def __enter__(self):
        return self.start()

    def __exit__(self, *_exc):
        self.stop()

    def start(self):
        self._listener.listen()
        self._spawn(self._accept)
        return self

    def stop(self):
        """Close the listener and every connection it accepted; wait for their threads."""
        self._stopping.set()
        self._listener.close()
        with self._lock:
            sockets, self._sockets = list(self._sockets), set()
        for sock in sockets:
            sock.close()
        for thread in self._threads:
            thread.join(1)
        self._threads = []

    # ---- threads ---------------------------------------------------------------
    def _spawn(self, run, *args):
        with self._lock:
            self._threads = [t for t in self._threads if t.is_alive()]
            thread = threading.Thread(target=run, args=args, daemon=True)
            self._threads.append(thread)
        thread.start()

    def _accept(self):
        while not self._stopping.is_set():
            try:
                client, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                if self._stopping.is_set():
                    return
                continue   # a peer reset its connection before accept() took it (WSAECONNRESET)
            with self._lock:
                self._sockets.add(client)
            self._spawn(self._serve, client)

    def _close(self, sock):
        with self._lock:
            self._sockets.discard(sock)
        sock.close()

    # ---- one connection --------------------------------------------------------
    def _serve(self, client):
        try:
            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            client.settimeout(5)
            while self._dispatch(client, self._read_head(client)):
                client.settimeout(None)   # kept alive: the next request is dispatched too
        except (OSError, ValueError):
            pass   # the peer went away, or stop() closed the socket under us
        finally:
            self._close(client)

    def _read_head(self, client):
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = client.recv(4096)
            if not chunk:
                raise ConnectionAbortedError("closed before the request head")
            head += chunk
        return head

    def _dispatch(self, client, head):
        """Answer one request; True if the client may send another on this connection."""
        request = head.split(b"\r\n", 1)[0].split(b" ")
        if (len(request) > 1 and request[0] == b"GET" and request[1].rstrip(b"/") == VERSION_PATH
                and local_host(head)):
            self._answer_version(client)
            return False
        return self._relay(client, head)

    def _answer_version(self, client):
        self.version_requests += 1
        with DIRECT.open("http://%s:%d/json/version" % (HOST, self.target_port), timeout=2) as response:
            body = BROWSER_NAME.sub(rb"\1Chrome/", response.read(), count=1)
        client.sendall(b"HTTP/1.1 200 OK\r\n"
                       b"Content-Type: application/json; charset=UTF-8\r\n"
                       b"Content-Length: %d\r\n"
                       b"Connection: close\r\n\r\n" % len(body) + body)

    def _relay(self, client, head):
        """Tunnel this request to the real port: a plain response is carried whole and the
        connection then takes the next request; a websocket stays up until a side hangs up."""
        self.relayed_requests += 1
        upgrade = b"upgrade: websocket" in head.lower()
        self.websocket_upgrades += upgrade
        target = socket.create_connection((HOST, self.target_port), timeout=2)
        with self._lock:
            self._sockets.add(target)
        try:
            target.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            target.settimeout(None)
            target.sendall(head)
            other = {client: target, target: client}
            seen, expected, forwarded = b"", None, 0
            while not self._stopping.is_set():
                for sock in select.select(list(other), [], [], 0.2)[0]:
                    data = sock.recv(65536)
                    if not data:
                        return False
                    other[sock].sendall(data)
                    if sock is target and not upgrade:
                        forwarded += len(data)
                        if expected is None:
                            seen += data
                            expected = response_length(seen)
                        if expected is not None and forwarded >= expected:
                            return True
            return False
        finally:
            self._close(target)
