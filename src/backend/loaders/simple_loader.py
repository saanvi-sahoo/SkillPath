import re
import os
import asyncio
import requests
import tempfile
from langchain_community.document_loaders import WebBaseLoader, TextLoader, PyPDFLoader

os.environ["USER_AGENT"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

async def load_url(link: str):
    loader = WebBaseLoader(link)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, loader.load)

async def download_gdrive_file(url: str, output_filename: str = "downloaded_file.pdf") -> str:
    if "drive.google.com/file/d/" in url:
        file_id = url.split("/file/d/")[1].split("/")[0]
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        
    response = requests.get(url)
    response.raise_for_status()
    
    with open(output_filename, "wb") as f:
        f.write(response.content)
        
    return os.path.abspath(output_filename)

async def read_gdrive_file_content(url: str):
    if "drive.google.com/file/d/" in url:
        file_id = url.split("/file/d/")[1].split("/")[0]
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        
    response = requests.get(url)
    response.raise_for_status()
    
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(response.content)
    temp_file.close() 
    
    try:
        with open(temp_file.name, 'rb') as file:
            content = file.read()
        return content
        
    finally:
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)

async def load_file(file_path: str):
    loader = TextLoader(file_path)
    return await loader.aload()

async def load_pdf(file_path: str):
    loader = PyPDFLoader(file_path)
    return await loader.aload()

async def main():
    print("Enter a URL or file path, press enter twice when done:")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
        
    user_input = "\n".join(lines).strip()

    is_url = re.match(r'^https?://', user_input)
    is_pdf = re.search(r'\.pdf$', user_input, re.IGNORECASE)
    is_google_file = re.search(r'drive\.google\.com/file/d/', user_input)
    
    docs = []

    if is_google_file:
        print("Detected Google Drive link...")
        
        
        gdrive_content = await read_gdrive_file_content(user_input)
        print("First 500 bytes \n")
        print(gdrive_content[:500])
        print("-----------------------------------------------------------------------------\n")
        
       
        local_path = await download_gdrive_file(user_input, "test_Resume_Temp.pdf")
        print("\n",local_path)
        docs = await load_pdf(local_path)
        
        if os.path.exists(local_path):
            os.remove(local_path)
            
    elif is_url:
        docs = await load_url(user_input)
        
    elif is_pdf:
        docs = await load_pdf(user_input)
            
    elif os.path.exists(user_input):
        docs = await load_file(user_input)
        
    else:
        print("Not a valid URL or file path.")
        return

    if docs:
        for doc in docs:
            print(doc.page_content[:500])

        with open("simple_loader.txt", "w", encoding="utf-8") as sl:
            sl.write(" ".join([doc.page_content for doc in docs]))
        print("\nSuccessfully wrote content to simple_loader.txt")
    else:
        print("No documents were loaded.")

if __name__ == "__main__":
    print("We are inside main and the program is running \n")
    asyncio.run(main())
    
    
###  https://drive.google.com/file/d/13W99AOXY37IMpKwQ9c_MPLWojOKdCW6g/view?usp=drive_link