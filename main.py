import gspread
import pandas as pd
import requests
from bs4 import BeautifulSoup
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
import openai
from googleapiclient.discovery import build
from google.oauth2 import service_account
from dotenv import load_dotenv
import os
import openai
from fastapi import FastAPI, HTTPException
from fastapi import FastAPI
from pydantic import BaseModel
import asyncio
import json
import re

app = FastAPI()

class RequestData(BaseModel):
    scrape_url: str
    keyword_url: str
    amazon_url: str
    product_url: str
    output_url:str

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
google_project_id = os.getenv("GOOGLE_PROJECT_ID")
google_private_key_id = os.getenv("GOOGLE_PRIVATE_KEY_ID")
google_private_key = os.getenv("GOOGLE_PRIVATE_KEY")
google_client_email = os.getenv("GOOGLE_CLIENT_EMAIL")
google_client_id = os.getenv("GOOGLE_CLIENT_ID")
google_auth_uri = os.getenv("GOOGLE_AUTH_URI")
google_token_uri = os.getenv("GOOGLE_TOKEN_URI")
google_cert_url = os.getenv("GOOGLE_CERT_URL")
google_x509_cert_url = os.getenv("GOOGLE_X509_CERT_URL")
DOCUMENT_ID = os.getenv("DOCUMENT_ID")

SCOPES = ["https://www.googleapis.com/auth/documents"]

google_credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
if not google_credentials_json:
    raise ValueError("GOOGLE_CREDENTIALS_JSON is not set in the .env file")
credentials_dict = json.loads(google_credentials_json)
credentials = service_account.Credentials.from_service_account_info(credentials_dict)
docs_service = build("docs", "v1", credentials=credentials)

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.get("/hi")
def hi():
    return {"message": "Hello World"}

@app.post("/fun1")
async def fun1(data:RequestData):
    try:
        title = await generate_amazon_title(data.product_url)
        return {"status": "success", "message": "Title generated successfully", "title":title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering functions: {e}")

@app.post("/fun2")
async def fun2(data:RequestData):
    try:
        description = await generate_amazon_description(data.product_url)
        return {"status": "success", "message": "description generated successfully", "description":description}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering functions: {e}")

@app.post("/fun3")
async def fun3(data:RequestData):
    try:
        bullets = await generate_amazon_bullets(data.product_url)
        return {"status": "success", "message": "bullets generated successfully", "bullets":bullets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering functions: {e}")

@app.post("/fun4")
async def fun4(data:RequestData):
    try:
        keywords = await generate_amazon_backend_keywords(data.product_url)
        return {"status": "success", "message": "keywords generated successfully", "keywords":keywords}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering functions: {e}")

@app.post("/fun5")
async def fun5(data:RequestData):
    try:
        match_and_create_google_sheet(credentials_file, data.amazon_url, data.scrape_url, data.output_url, data.product_url)
        print("values in func5 is")
        print(data.amazon_url)
        print(data.scrape_url)
        print(data.output_url)
        print(data.product_url)
        return {"status": "success", "message": "google sheet generated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering functions: {e}")


@app.post("/fun6")
async def fun6(data:RequestData):
    try:
         scrape_product_info(data.product_url)
         return {"status": "success", "message": "google sheet generated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering functions: {e}")
        



@app.get("/trigger")
@app.post("/trigger")
async def trigger_functions(data: RequestData):
    try:
        print("Received Data:")
        print(f"Amazon Sheet URL: {data.amazon_url}")
        print(f"Scrape Sheet URL: {data.scrape_url}")
        print(f"Output Sheet URL: {data.output_url}")
        print(f"Product URL: {data.product_url}")

        print("Generating Google Sheet:")

        match_and_create_google_sheet(credentials_file, data.amazon_url, data.scrape_url, data.output_url, data.product_url)
       
        print("Generating Google Docs:")
        await generate_amazon_backend_keywords(data.product_url)
        await generate_amazon_bullets(data.product_url)
        await generate_amazon_description(data.product_url)
        await generate_amazon_title(data.product_url)
        print("Results Generated")
        return {
            "status": "success", 
            "message": "All content generated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering functions: {e}")

def append_to_google_doc(doc_id, text):
    """Append text to a Google Doc."""
    requests = [
        {
            "insertText": {
                "location": {"index": 1},
                "text": text + "\n\n"
            }
        }
    ]
    docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

def authenticate_gspread(credentials_file):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    return gspread.authorize(creds)

def get_google_sheet_data(gc, sheet_url):
    sheet = gc.open_by_url(sheet_url).sheet1
    df = get_as_dataframe(sheet, evaluate_formulas=True, skip_blank_rows=True)
    return df.dropna(how="all")

def scrape_product_info(product_url):
    """Extracts ALL text from the product page, removing excessive whitespace."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        response = requests.get(product_url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to fetch product page: {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, "html.parser")
        all_text = soup.get_text(separator=" ").lower()
        cleaned_text = re.sub(r'\s+', ' ', all_text).strip()
        return cleaned_text
    except Exception as e:
        print(f"Error scraping product info: {e}")
        return None


def get_top_matches(product_info, field_name, field_value, possible_values):
    """Uses OpenAI to find the best matches for a given field from the product description."""
    ai_prompt = f"""
    You are an AI specializing in product attribute matching.

    ### Product Information:
    {product_info}

    ### Field Name:
    {field_name}

    ### Field Value (Reference from Amazon Sheet):
    {field_value}

    ### Possible Options (from the Google Sheet):
    {', '.join(possible_values)}

    ### Instructions:
    - Compare the field value against the product description.
    - From the possible options, pick up to **5 best matches** that are most relevant.
    - Output only the matches as a **comma-separated list** with no extra text.
    - If no good matches exist, return an **empty string**.
    """

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": ai_prompt}]
    )
    
    matches = response.choices[0].message.content.strip().split(", ")
    return [match for match in matches if match]

    
def match_and_create_google_sheet(credentials_file, amazon_url, scrap_url, output_url, product_url):
    """Main function to process field matching and update Google Sheets."""
    gc = authenticate_gspread(credentials_file)
    
    amazon_df = get_google_sheet_data(gc, amazon_url)
    scrap_df = get_google_sheet_data(gc, scrap_url)
    scraped_text = scrape_product_info(product_url)
    
    if scraped_text is None:
        return "Scraping failed."
    
    amazon_fields = set(amazon_df.iloc[1:, 0].dropna())
    scrap_fields = set(scrap_df.iloc[1:, 0].dropna())
    matching_fields = list(amazon_fields.intersection(scrap_fields))
    
    if not matching_fields:
        return "No matching fields found."
    
    matched_data = {"Field Name": [], "Value": [], "AI Best Matched 1": [], "AI Best Matched 2": [], "AI Best Matched 3": [], "AI Best Matched 4": [], "AI Best Matched 5": []}
    
    for field in matching_fields:
        matched_data["Field Name"].append(field)
        
        value = amazon_df.loc[amazon_df.iloc[:, 0] == field].iloc[:, 1].values
        matched_value = value[0] if len(value) > 0 else ""
        
        possible_options = scrap_df.loc[scrap_df.iloc[:, 0] == field].iloc[:, 1].dropna().tolist()
        
        ai_matches = get_top_matches(scraped_text, field, matched_value, possible_options)
        
        ai_matches = ai_matches[:5] + [""] * (5 - len(ai_matches))  # Ensure 5 matches
        
        matched_data["Value"].append(matched_value)
        matched_data["AI Best Matched 1"].append(ai_matches[0])
        matched_data["AI Best Matched 2"].append(ai_matches[1])
        matched_data["AI Best Matched 3"].append(ai_matches[2])
        matched_data["AI Best Matched 4"].append(ai_matches[3])
        matched_data["AI Best Matched 5"].append(ai_matches[4])

    matched_df = pd.DataFrame(matched_data)
    output_sheet = gc.open_by_url(output_url).worksheet("Test")
    values = [matched_df.columns.tolist()] + matched_df.values.tolist()
    output_sheet.insert_rows(values, row=1)
    
    return f"Updated Google Sheet: {output_url} (Sheet: Test)"


credentials_file = "google-credentials.json"
client = openai.OpenAI(api_key=api_key)

async def generate_amazon_title(product_url):
    title_prompt = f"""
    You are an expert in writing Amazon product titles optimized for search and conversions.  
    Your task is to generate a compelling, keyword-rich title using the exact product details provided.  

    ### Important Instructions:
    - **Do not assume** the size, volume, or weight—use the exact details provided.  
     **ONLY use the words EXACTLY as they appear in the product name and description.**  
    - Extract the main **product name and brand** (if available).  
    - Include **size, volume (e.g., "9oz"), weight, material, and key features** exactly as they appear.  
    - Use commonly searched keywords relevant to the product.  
    - Keep it concise, **within Amazon's 200-character limit**.  
    - **JUST return the Amazon-style product title with no extra text.**  

    **URL:** {product_url}
    """

    try:
        response = await asyncio.to_thread(client.chat.completions.create,
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are an expert in writing Amazon product titles."},
                {"role": "user", "content": title_prompt}
            ]
        )
        title = response.choices[0].message.content.strip()
        print("Generated Amazon Product Title")
        append_to_google_doc(DOCUMENT_ID, f"Amazon Product Title:\n{title}")
        return title
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating title: {str(e)}")

async def generate_amazon_bullets(product_url):
    bullets_prompt = f"""
    Act as an Amazon SEO expert. Extract **ONLY** verified product details from the provided data—no assumptions, no extra words.  
    Generate **five bullet points** highlighting the **key features and benefits** exactly as described in the product details.  

    ✅ **STRICT ACCURACY**: Use **only** words found in the product data. **Do NOT assume or invent features.**  
    ✅ **FIXED LENGTH**: Each bullet **must be between 210 and 230 characters EXCLUDING the capital words.**  
    ✅ **AMAZON COMPLIANT**: No false claims, redundancy, or keyword stuffing.  
    ✅ **SCANNABLE FORMAT**: Start each bullet with a **capitalized key feature** (e.g., `"DURABLE MATERIAL: High-quality..."`).  
    ✅ **READABILITY**: Use sentence case, keeping it clear and benefit-driven.  

    Write straight to the point and **do not include introductory text** like "here are bullet points." Each bullet should be **exactly** within the required character limit.

    Example Output:  
    ✔ **PREMIUM MATERIAL**: Made from ultra-soft, breathable cotton that enhances airflow and ensures a gentle touch on the skin. Provides superior comfort and long-lasting durability, making it ideal for sensitive skin and everyday wear.  

    ✔ **SUPERIOR FIT & COMFORT**: Expertly tailored for a snug yet flexible fit that adapts to movement without irritation. Designed for all-day comfort, making it perfect for work, travel, lounging, or an active lifestyle while maintaining breathability.  

    ✔ **DURABLE & LONG-LASTING**: High-quality fabric with reinforced stitching resists wear and tear, ensuring extended use without fading or shrinking. Retains softness, shape, and strength even after multiple washes, offering reliable durability over time.  

    ✔ **MOISTURE-WICKING TECHNOLOGY**: Advanced moisture-wicking fabric quickly absorbs sweat and allows it to evaporate, keeping you dry and fresh all day. Designed for workouts, hot climates, and daily wear, ensuring maximum breathability and temperature control.  

    ✔ **VERSATILE FOR ANY OCCASION**: Ideal for casual wear, workouts, travel, or lounging at home. Blends comfort and function effortlessly while pairing well with any outfit, making it a must-have staple that adapts to any season or setting with ease.  

    ### **Product Information:**  
    {product_url}  
    """
    try:
        response = await asyncio.to_thread(client.chat.completions.create,
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are an expert in writing Amazon product bullet points."},
                {"role": "user", "content": bullets_prompt}
            ]
        )
        bullets = response.choices[0].message.content.strip()
        print("Generated Amazon Bullet Points")
        append_to_google_doc(DOCUMENT_ID, f"Amazon Bullet Points:\n{bullets}")
        return bullets
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating bullets: {str(e)}")

async def generate_amazon_backend_keywords(product_url):
    keywords_prompt = f"""
    please make sure to generate a total of 500 keywords, dont write more or less
    Amazon SEO Backend Keywords Prompt (500 Characters, No Repetition, High Conversion, Feature-Focused)
    Act as an Amazon SEO expert. Generate a backend keyword string of exactly 500 characters to maximize product discoverability while following Amazon’s guidelines.

    Instructions:
    1️⃣ Extract Unique, High-Relevance Keywords, No Repetition, High Conversion, Feature-Focused from keywords doc/product url whatever is available
    Dont assume anything, if its not written in the provided data then dont write it
    Remove redundant, closely related, or duplicate keywords (e.g., avoid both "organic shampoo" and "shampoo organic").

    2️⃣ Follow Amazon’s Backend Keyword Policies
    ✅ dont add any commas – Separate keywords with spaces.
    ✅ No competitor brand names, ASINs, or promotional claims (e.g., avoid "best shampoo," "top-rated").
    ✅ No redundant or overlapping keywords.

    3️⃣ Maximize Discoverability & Conversion Potential
    Include synonyms, regional spellings, and related terms customers might search for.
    Cover product variations, use cases, and relevant attributes (e.g., size, material, scent, key ingredients).
    Use alternative terms and phrasing to expand search reach.
    Maintain high relevance without repetition or unnecessary words.
    **Product Information:**
    {product_url}
    """

    try:
        if not product_url:
            return "Failed to generate backend keywords: No product data found"
        response = await asyncio.to_thread(client.chat.completions.create,
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": keywords_prompt}]
        )
        
        backend_keywords = response.choices[0].message.content.strip()
        print("Generated Amazon Product Keywords")
        backend_keywords = backend_keywords.replace(",", " ")  
        match = re.match(r'^(.{1,500})\b', backend_keywords)
        short_keywords = match.group(1) if match else backend_keywords[:500] 
        append_to_google_doc(DOCUMENT_ID, f"Amazon Keywords:\n{short_keywords}")


        return backend_keywords
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating keywords: {str(e)}")

async def generate_amazon_description(product_url):
    description_prompt = f"""
    Act as an Amazon copywriting expert with 10+ years of experience crafting high-converting, SEO-optimized product
    descriptions that maximize visibility and drive sales.
    Your task is to generate a clear, engaging, and persuasive product description that highlights the product’s 
    unique features and key benefits while seamlessly integrating high-ranking keywords.
    Extract all product details ONLY from the provided URL—do NOT assume or fabricate any information.
    If an ingredient, feature, or specification is NOT mentioned, do not include it in the description.

    Instructions:
    ✅ USE SINGLE PARAGRAPH FOR WRITING, DONT INCLUDE NEXT LINES OR ICONS
    ✅ Identify key benefits, materials, specifications, and unique selling points while maintaining a professional and persuasive tone.
    ✅ Do NOT generate or invent customer reviews, quotes, or ratings.
    ✅ Use concise, benefit-driven bullet points to enhance readability.
    ✅ Ensure the description is SEO-optimized, short and to the point by naturally integrating relevant keywords.
    ✅ NO headings (e.g., "Product Description," "Key Features").
    How to Structure the Description:
    Start with a compelling hook that immediately captures attention.
    Clearly define what the product does and why it’s valuable
    Write 3-5 key benefits, keeping each concise yet impactful.
    Highlight 1-2 unique selling points that differentiate this product.
    Provide reassurance on quality, durability, and effectiveness.
    Now, generate a compelling Amazon product description based ONLY on verified product details. Do not fabricate ingredients, materials, reviews, or features that aren’t explicitly provided. 
    **Product Information:**
    {product_url}

    eg: Amazon Product Description: 
    Transform your hair care routine with our Natural Shampoo, crafted with the finest ingredients to deliver exceptional results. Gently cleanses hair without stripping natural oils, ensuring a fresh and healthy feel. Nourishes and strengthens hair from root to tip, enhancing overall texture and shine. Promotes a healthy scalp while preventing dryness and irritation, supporting long-term hair wellness. Infused with botanical extracts to provide a refreshing and revitalizing experience after every wash. Free from harsh chemicals, sulfates, and parabens, making it a safe and effective choice for all hair types. Formulated to uphold the highest standards of quality, ensuring long-lasting effectiveness and noticeable improvement in hair health. Elevate your hair care regimen with nature’s best ingredients.
 
 """
    try:
        """Generates an SEO-optimized Amazon product description."""
        if not product_url:
            return "Failed to generate product description: No product data found"
        response = await asyncio.to_thread(client.chat.completions.create,
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": description_prompt}]
        )
        
        optimized_description = response.choices[0].message.content.strip()
        print("Generated Amazon Product Description")
        append_to_google_doc(DOCUMENT_ID, f"Amazon Product Description:\n{optimized_description}")
        return optimized_description
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating description: {str(e)}")

credentials_file = "google-credentials.json"
client = openai.OpenAI(api_key=api_key)
# def match_and_create_google_sheet(credentials_file, amazon_url, scrap_url, output_url, product_url):
#     gc = authenticate_gspread(credentials_file)
    
#     # Load Amazon and Scrap Data
#     amazon_df = get_google_sheet_data(gc, amazon_url)
#     scrap_df = get_google_sheet_data(gc, scrap_url)
    
#     amazon_fields = set(amazon_df.iloc[1:, 0].dropna())
#     scrap_fields = set(scrap_df.iloc[1:, 0].dropna())
#     matching_fields = list(amazon_fields.intersection(scrap_fields))
    

#     if matching_fields:
#         matched_data = {"Field Name": [], "Value": [], "AI Best Matched 1": [], "AI Best Matched 2": [], "AI Best Matched 3": [], "AI Best Matched 4": [], "AI Best Matched 5": []}
        
#         for field in matching_fields:
#             matched_data["Field Name"].append(field)
            
#             # Get the corresponding "Value" from the Amazon sheet
#             value = amazon_df.loc[amazon_df.iloc[:, 0] == field].iloc[:, 1].values
#             matched_value = value[0] if len(value) > 0 else ""
            
#             # Get possible options from Scrap sheet
#             possible_options = scrap_df.loc[scrap_df.iloc[:, 0] == field].iloc[:, 1].dropna().tolist()
            
#             # AI Matching using the updated method
#             ai_matches = get_top_matches(product_summary, field, matched_value, possible_options) 
            
#             # Ensure there are exactly 5 matches (if fewer, leave empty)
#             ai_matches = ai_matches[:5]  # Get only the first 5 matches
#             ai_matches += [""] * (5 - len(ai_matches))  # Pad with empty strings if less than 5 matches
            
#             matched_data["Value"].append(matched_value)
#             matched_data["AI Best Matched 1"].append(ai_matches[0])
#             matched_data["AI Best Matched 2"].append(ai_matches[1])
#             matched_data["AI Best Matched 3"].append(ai_matches[2])
#             matched_data["AI Best Matched 4"].append(ai_matches[3])
#             matched_data["AI Best Matched 5"].append(ai_matches[4])

#         matched_df = pd.DataFrame(matched_data)

#         # Write to Google Sheets without deleting existing data
#         output_sheet = gc.open_by_url(output_url).worksheet("Test")
#         values = [matched_df.columns.tolist()] + matched_df.values.tolist()
#         output_sheet.insert_rows(values, row=1)
#         print(f"New matching fields with values have been inserted at the top of the Google Sheet: {output_url} (Sheet: Test)")
#     else:
#         print("No matching fields found.")


# amazon_sheet_url = "https://docs.google.com/spreadsheets/d/1A3SW1gqTQrB0Z5jGm0PcNQJnw2IcGFHuZd1aRPLt8ZQ/edit"
# scrap_sheet_url = "https://docs.google.com/spreadsheets/d/18UoIYMIzRXZzsWX12oTsEk13W3jTA9oTd_kT-iSQb4c/edit"
# output_sheet_url = "https://docs.google.com/spreadsheets/d/1At_QcMag0-jsEhoyMhhAPb1e_uUO26p56s9hX9-81rk/edit"
# product_url = "https://www.naturesustained.com/products/natural-shampoo?variant=44673198489761"
# product_url = "https://www.amazon.com/Gold-Bond-Ultimate-Intensive-Healing/dp/B00A8S6HM4/ref=zg_bs_g_11062261_d_sccl_1/138-3959840-0947826?th=1"
# product_url = "https://www.amazon.com/OKeeffes-Working-Hands-Cream-ounce/dp/B00121UVU0/ref=zg_bs_g_11062261_d_sccl_5/138-3959840-0947826?th=1" 
# product_url = "https://www.amazon.com/Vaseline-Intensive-Care-Lotion-Soothe/dp/B01HTJTV0E/ref=zg_bs_g_11062261_d_sccl_15/138-3959840-0947826?th=1"

# title_prompt = f"""
#     You are an expert in writing Amazon product titles optimized for search and conversions.  
#     Your task is to generate a compelling, keyword-rich title using the exact product details provided.  

#     ### Important Instructions:
#     - **Do not assume** the size, volume, or weight—use the exact details provided.  
#     - Extract the main **product name and brand** (if available).  
#     - Include **size, volume (e.g., "9oz"), weight, material, and key features** exactly as they appear.  
#     - Use commonly searched keywords relevant to the product.  
#     - Keep it concise, **within Amazon's 200-character limit**.  
#     - **JUST return the Amazon-style product title with no extra text.**  

#     **URL:** {product_url}
#     """
# bullets_prompt = f"""
#     Act as an Amazon SEO expert and high-converting content writer with 10+ years of experience crafting bullet points that maximize conversion rates (CVR) and sales. Your objective is to create five compelling, SEO-optimized bullet points that effectively highlight key features, emphasize benefits, and incorporate high-impact keywords while ensuring readability and compliance with Amazon’s guidelines.

#     Instructions:
#     ✅ Strict Accuracy & Compliance
#     DO NOT assume product details—extract verified information only.
#     Maintain strict Amazon compliance (no false claims, customer reviews, keyword stuffing, or unverified details).
#     Use sentence case (Amazon’s style guideline).

#     ✅ Benefit-Driven, Engaging Writing
#     Prioritize customer benefits over technical specs.
#     Keep it concise yet persuasive, ensuring each bullet adds value without unnecessary fluff.
#     Start each bullet with a capitalized key feature for scannability (e.g., "PREMIUM MATERIAL: Soft, breathable fabric for all-day comfort.").

#     ✅ Optimized for Amazon SEO Without Overstuffing
#     Integrate high-impact keywords naturally—avoid forced or excessive keyword stuffing.
#     Write for both human readability and Amazon’s A9 algorithm, ensuring the best balance of engagement and search visibility.

#     ✅ Concise, Scannable, and Unique Bullet Points
#     Limit each bullet to 200 characters for optimal readability.
#     Ensure each bullet highlights a distinct feature or benefit—no overlap or redundancy.
#     Use a logical progression that enhances product appeal and user understanding.

#     write straigh to the point and no extra text like "here are bullet points" 
#     Example Output:
#     ✔ PREMIUM MATERIAL: Crafted from ultra-soft, breathable cotton for all-day comfort and durability. Perfect for sensitive skin.

#     ✔ SUPERIOR FIT & COMFORT: Tailored design ensures a perfect fit without irritation, making it ideal for everyday wear.

#     ✔ DURABLE & LONG-LASTING: Reinforced stitching enhances durability, ensuring long-lasting wear even after multiple washes.

#     ✔ MOISTURE-WICKING TECHNOLOGY: Advanced fabric wicks away sweat, keeping you cool and dry in any season.

#     ✔ VERSATILE FOR ANY OCCASION: Perfect for casual outings, workouts, or lounging at home—designed for ultimate versatility.
#     ### **Product Information:**
#     """


# keywords_prompt = f"""
#     please make sure to generate a total of 500 keywords, dont write more or less
#     Amazon SEO Backend Keywords Prompt (500 Characters, No Repetition, High Conversion, Feature-Focused)
#     Act as an Amazon SEO expert. Generate a backend keyword string of exactly 500 characters to maximize product discoverability while following Amazon’s guidelines.

#     Instructions:
#     1️⃣ Extract Unique, High-Relevance Keywords, No Repetition, High Conversion, Feature-Focused from keywords doc/product url whatever is available
#     Dont assume anything, if its not written in the provided data then dont write it
#     Remove redundant, closely related, or duplicate keywords (e.g., avoid both "organic shampoo" and "shampoo organic").

#     2️⃣ Follow Amazon’s Backend Keyword Policies
#     ✅ dont add any commas – Separate keywords with spaces.
#     ✅ No competitor brand names, ASINs, or promotional claims (e.g., avoid "best shampoo," "top-rated").
#     ✅ No redundant or overlapping keywords.

#     3️⃣ Maximize Discoverability & Conversion Potential
#     Include synonyms, regional spellings, and related terms customers might search for.
#     Cover product variations, use cases, and relevant attributes (e.g., size, material, scent, key ingredients).
#     Use alternative terms and phrasing to expand search reach.
#     Maintain high relevance without repetition or unnecessary words.
#     **Product Information:**
#     """

 

# description_prompt = f"""
#     Act as an Amazon copywriting expert with 10+ years of experience crafting high-converting, SEO-optimized product
#     descriptions that maximize visibility and drive sales.
#     Your task is to generate a clear, engaging, and persuasive product description that highlights the product’s 
#     unique features and key benefits while seamlessly integrating high-ranking keywords.
#     Extract all product details ONLY from the provided URL—do NOT assume or fabricate any information.
#     If an ingredient, feature, or specification is NOT mentioned, do not include it in the description.

#     Instructions:
#     ✅ Identify key benefits, materials, specifications, and unique selling points while maintaining a professional and persuasive tone.
#     ✅ Do NOT generate or invent customer reviews, quotes, or ratings.
#     ✅ Use concise, benefit-driven bullet points to enhance readability.
#     ✅ Ensure the description is SEO-optimized, short and to the point by naturally integrating relevant keywords.
#     ✅ NO headings (e.g., "Product Description," "Key Features").
#     How to Structure the Description:
#     Start with a compelling hook that immediately captures attention.
#     Clearly define what the product does and why it’s valuable.
#     List 3-5 key benefits, keeping each concise yet impactful.
#     Highlight 1-2 unique selling points that differentiate this product.
#     Provide reassurance on quality, durability, and effectiveness.
#     Now, generate a compelling Amazon product description based ONLY on verified product details. Do not fabricate ingredients, materials, reviews, or features that aren’t explicitly provided. 
#     **Product Information:**
#  """

#   Act as an Amazon SEO expert and high-converting content writer specializing in this industry. With 10+ years of experience, your objective is to craft five compelling, SEO-optimized bullet points for an Amazon product listing. These bullet points should effectively highlight key features, emphasize benefits, and incorporate high-impact keywords to enhance customer engagement, readability, and discoverability. The ultimate goal is to maximize conversion rate (CVR) and drive sales.

#     Instructions:
#     1. Identify & Highlight Key Features  
#     - Extract the most compelling product features from the provided description and focus each bullet point on a distinct feature.  
#     - Showcase how each feature addresses customer needs, solves pain points, or enhances the user experience.  
#     - Use persuasive, benefit-driven language that resonates with the target audience.  

#     2. Integrate High-Impact Keywords Naturally  
#     - Utilize highly relevant, high-search-volume keywords from Amazon search trends without keyword stuffing.  
#     - Maintain natural readability while optimizing for search rankings, ensuring compliance with Amazon's guidelines.  

#     3. Prioritize Benefits Over Features  
#     - Transform technical features into customer-centric benefits.  
#     - Example: Instead of "Waterproof Design," write "WATERPROOF DESIGN: Stay dry in any weather with a fully waterproof build, ideal for outdoor adventures."  

#     4. Structure for Readability & Engagement  
#     - Format: Start each bullet point with a capitalized key feature for clarity (e.g., "PREMIUM MATERIAL: …").  
#     - Tone: Maintain a professional, engaging, and persuasive style.  
#     - Flow: Ensure a logical progression across the five points, covering unique aspects without redundancy.  

#     5. Character Limit & Formatting  
#     - Keep each bullet point within 200 characters for optimal readability.  
#     - Ensure content is concise, scannable, and easy to understand at a glance.  

#     Take a deep breath and approach this step-by-step, ensuring each bullet point is optimized for impact, clarity, and conversion.

# description_prompt = f"""
#     Act as an Amazon copywriting expert with 10+ years of experience crafting high-converting, SEO-optimized product descriptions 
#     that enhance product visibility and drive sales. Your goal is to create a clear, engaging, and persuasive product description 
#     that highlights the product's unique features and key benefits while seamlessly integrating relevant keywords to improve search rankings and sales volumes.
    
#     Step 1: Research the Product from URLs:
#     - Extract all relevant product information from the provided URLs.
#     - Identify key features, benefits, materials, specifications, and unique selling points.
#     - Understand the target audience and intended use cases.
#     - Note any customer reviews or feedback to identify common pain points or standout benefits.
    
#     Step 2: Write the Product Description:
#     - **Engaging Introduction**: Begin with a compelling hook that immediately grabs the reader's attention.
#     - Clearly define the product's primary purpose and the key problem it solves.
#     - Use powerful adjectives and action-driven language to make it emotionally appealing.
    
#     - **Key Features & Benefits**: List each feature concisely, followed by a short, benefit-driven explanation.
#     - Prioritize clarity, avoiding jargon while maintaining a professional and trustworthy tone.
#     - Integrate relevant Amazon SEO keywords naturally for better visibility from the "Keyword Doc."
    
#     - **Unique Selling Points**: Emphasize 1-2 standout features that set this product apart from competitors.
#     - Highlight any special materials, advanced technology, or unique design elements.
#     - Use persuasive language to make these points memorable.
    
#     - **Usage & Versatility**: Explain who the product is ideal for (e.g., busy professionals, parents, athletes, kids).
#     - Mention multiple use cases or settings where this product excels.
#     - Provide reassurance on ease of use, durability, or effectiveness.

#     ### **Product URL:**  
#     {product_url}
#     """


   # Act as an Amazon SEO expert. Generate a **single** backend keyword string (100 characters max) that maximizes discoverability while strictly following Amazon's guidelines.

    # **Instructions:**
    # **Extract Unique, High-Relevance Keywords**
    # - Use only high-converting, relevant keywords from the "Keyword Doc"
    # - Use the "URLs" to learn about the product to choose 100% relevant keywords.
    # - Remove duplicate or closely related terms (e.g., exclude both "organic shampoo" and "shampoo organic").

    # **Follow Amazon's Backend Keyword Policies**
    # ✅ No Commas – Separate keywords with spaces for full character efficiency.
    # ✅ No Competitor Brand Names, ASINs, or Promotional Claims (e.g., avoid "best shampoo," "top-rated").
    # ✅ No Redundant or Overlapping Keywords (e.g., avoid using both "dandruff shampoo" and "anti-dandruff shampoo").

    # **Prioritize Broad Discoverability & Conversion Potential**
    # - Include synonyms, regional spellings, and related terms customers might search for.
    # - Cover different customer pain points (e.g., "itchy scalp relief," "hair regrowth").
    # - Expand with related but distinct keywords that increase exposure across multiple search queries.

    # **Utilize STRICTLY 200 CHARACTERS Limit Without Wasting Space**
    # - Include product variations, use cases, and relevant attributes (e.g., size, material, color, features).
    # - Include problem-solution keywords (hydrating, clarifying, scalp care).
    # - Use alternative terms and phrasing for broader search inclusion.


    # **Instructions:**
    # - Extract only high-converting, relevant keywords from the product page.
    # - No commas, separate keywords with spaces.
    # - No competitor brand names, ASINs, or promotional claims.
    # - No redundant or overlapping keywords.
    # - Utilize synonyms, regional spellings, and alternative terms.
    # - Prioritize broad discoverability & conversion potential.
    # - Ensure the final output is exactly **200 characters** long.



# match_and_create_google_sheet(credentials_file, amazon_sheet_url, scrap_sheet_url, output_sheet_url, product_url)
# generate_amazon_backend_keywords()
# generate_amazon_bullets()
# generate_amazon_description()
# generate_amazon_title()

# SERVICE_ACCOUNT_FILE = "google-credentials.json"

# credentials = service_account.Credentials.from_service_account_file(
#     SERVICE_ACCOUNT_FILE, scopes=SCOPES
# )
# docs_service = build("docs", "v1", credentials=credentials)

 
    #  Act as an Amazon SEO expert with 10+ years of experience crafting bullet 
    # points for maximum conversion rates (CVR) and sales. Your objective is to create five compelling, 
    # SEO-optimized bullet points keeping in mind the following instructions:
    #   that effectively highlight key features, emphasize benefits, and incorporate 
    # high-impact keywords while ensuring readability and compliance with Amazon’s guidelines.

    # Instructions:
    # write key features, benefits, use high impact words(which are present in the product data)
    # DO NOT assume product details. Only extract from data available in the product shared ensuring readability.
    # Maintain strict Amazon compliance (no false claims, no redundancy, customer reviews, keyword stuffing, or unverified details).
    # Use sentence case (Amazon’s style guideline).
    # Prioritize customer benefits over technical specs.
    # Keep it concise yet persuasive
    # Start each bullet with a capitalized key feature for scannability (e.g., "PREMIUM MATERIAL: Soft, breathable fabric for all-day comfort.").
    # Limit each bullet to 200 characters for optimal readability.

    # write straigh to the point and no extra text like "here are bullet points" 
    # Example Output:
    # ✔ PREMIUM MATERIAL: Crafted from ultra-soft, breathable cotton for all-day comfort and durability. Perfect for sensitive skin.

    # ✔ SUPERIOR FIT & COMFORT: Tailored design ensures a perfect fit without irritation, making it ideal for everyday wear.

    # ✔ DURABLE & LONG-LASTING: Reinforced stitching enhances durability, ensuring long-lasting wear even after multiple washes.

    # ✔ MOISTURE-WICKING TECHNOLOGY: Advanced fabric wicks away sweat, keeping you cool and dry in any season.

    # ✔ VERSATILE FOR ANY OCCASION: Perfect for casual outings, workouts, or lounging at home—designed for ultimate versatility.
    # ### **Product Information:**
    # {product_url}