import xml.etree.ElementTree as ET

def read_file(file_path):
    with open(file_path, "rb", buffering=0) as f:
        return f.read().decode("utf-8")  # or the correct encoding
# Your XML string
def xml_to_json(path):
    # xml_data = read_file(r'C:\Users\arshi\OneDrive\Desktop\code\glasscode\hex\1.CD2')
    xml_data = read_file(f'{path}')
    # print(xml_data)
    # Parse XML
    wrapped_xml = f"<root>{xml_data}</root>"
    root = ET.fromstring(wrapped_xml)
    # print(root)

    # # Extract data
    result = []

    lines = root.find("lines")

    count_tag = lines.find('count')
    count = count_tag.text

    for i in range(int(count)):
        line = lines.find('line'+str(i+1))
        desc = line.find('description').text
        if desc == 'Premium 98': #TO BE CHANGED
            desc = "Premium Unleaded"
        # if desc == 'Miscellaneous': #TO BE CHANGED
        #     desc = "Diesel"
        # if desc == 'Miscellaneous': #TO BE CHANGED
        #     desc = "Premium Unleaded"
        
        quantity = line.find('quantity').text
        sub_after_tax = line.find('subaftertax').text
        result.append({"description":desc, "quantity":quantity, "subaftertax":sub_after_tax})
        
    return result

def hasSalenotes(path):
    # xml_data = read_file(r'C:\Users\arshi\OneDrive\Desktop\code\glasscode\hex\1.CD2')
    xml_data = read_file(f'{path}')
    # print(xml_data)
    # Parse XML
    wrapped_xml = f"<root>{xml_data}</root>"
    root = ET.fromstring(wrapped_xml)
    # print(root)

    # # Extract data
    result = []
    # print(root.find('salecapture'))
    # lines = root.find("lines")
    if root.find('salecapture'): 
        return True
    return False


def hasPayments(path):
    # xml_data = read_file(r'C:\Users\arshi\OneDrive\Desktop\code\glasscode\hex\1.CD2')
    xml_data = read_file(f'{path}')
    # print(xml_data)
    # Parse XML
    wrapped_xml = f"<root>{xml_data}</root>"
    root = ET.fromstring(wrapped_xml)
    # print(root)

    # # Extract data
    result = []

    # lines = root.find("lines")
    if root.find('payments'): return True
    return False
# print(xml_to_json())

def isEmpty(path):
    # xml_data = read_file(r'C:\Users\arshi\OneDrive\Desktop\code\glasscode\hex\1.CD2')
    xml_data = read_file(f'{path}')
    # print(xml_data)
    wrapped_xml = f"<root>{xml_data}</root>"
    root = ET.fromstring(wrapped_xml)
    # print(root)

    # # Extract data
    result = []

    lines = root.find("lines")

    count_tag = lines.find('count')
    count = count_tag.text
    return int(count) == 0

# hasSalenotes(r"C:\InfinityPOS\1.CD2")

# def read_file():
#     abs_path = r'C:\InfinityPOS\1.CD2'  # raw string avoids backslash issues
#     with open(abs_path, "r", encoding='utf-8') as file:
#         return file.read()
# import time
# from datetime import datetime
# # prev=""

# start_time=datetime.now()
# while True:
#     if not prev:
#         prev= read_file()
#     else:
#         if not read_file() == prev:
#             time_diff = datetime.now()-start_time
#             print(time_diff.total_seconds())
#             print("----------------")
#             print(read_file())
#             prev = read_file()
#     time.sleep(1)


