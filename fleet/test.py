# import xml.etree.ElementTree as ET

# def read_file(file_name):
#     result = ""
#     with open(file_name, "r") as file:
#         lines = file.readlines()

#         for line in lines:
#             result += line.strip()+'\n'
#     return result
# # Your XML string
# def xml_to_json(path):
#     # xml_data = read_file(r'C:\Users\arshi\OneDrive\Desktop\code\glasscode\hex\1.CD2')
#     xml_data = read_file(f'{path}')
#     # print(xml_data)
#     # Parse XML
#     wrapped_xml = f"<root>{xml_data}</root>"
#     root = ET.fromstring(wrapped_xml)
#     # print(root)

#     # # Extract data
#     result = []

#     # lines = root.find("lines")
#     return root.find('salenotes')
# #     count_tag = lines.find('count')
# #     count = count_tag.text

# #     for i in range(int(count)):
# #         line = lines.find('line'+str(i+1))
# #         desc = line.find('description').text
# #         if desc == 'Premium 98': #TO BE CHANGED
# #             desc = "Premium Unleaded"
# #         if desc == 'Miscellaneous': #TO BE CHANGED
# #             desc = "Premium Unleaded"
        
# #         quantity = line.find('quantity').text
# #         sub_after_tax = line.find('subaftertax').text
# #         result.append({"description":desc, "quantity":quantity, "subaftertax":sub_after_tax})
        
# #     return result

# print(xml_to_json("C:/InfinityPOS/1.CD2"))


import pyautogui
import time

try:
    while True:
        x, y = pyautogui.position()
        print(f"Mouse position: ({x}, {y})", end='\r')  # Overwrites line in terminal
        time.sleep(0.1)  # Update every 0.1 seconds
except KeyboardInterrupt:
    print("\nTracking stopped.")
