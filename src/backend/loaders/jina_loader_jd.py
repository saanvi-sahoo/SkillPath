import httpx
import asyncio

async def get_job_description(url):
    jina_url = f"https://r.jina.ai/{url}"
    
    try:
        
        async with httpx.AsyncClient(timeout=15.0) as client:
           
            response = await client.get(jina_url)
            response.raise_for_status()
            
            #
            return response.text
            
    except httpx.HTTPError:
        print("Error: Could not connect or fetch the page.")
        return None
    except Exception:
        print("Error: An unexpected issue occurred.")
        return None

async def main():
    target_url = input("Enter the job description URL: ").strip()
    
    if target_url:
        
        markdown_result = await get_job_description(target_url)
        
        if markdown_result:
            
            with open("jd_clean_text.txt","w",encoding="utf-8")as file:
                file.write(markdown_result)
            
            print("\n saved in file as jd_clean_text.txt")
            print("\n" + markdown_result)
    else:
        print("No URL was provided.")

if __name__ == "__main__":
    
    asyncio.run(main())