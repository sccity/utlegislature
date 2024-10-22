import requests
import re

# Helper function to extract the date from the svotes.jsp or mtgvotes.jsp page
def extract_vote_date(text):
    match = re.search(r'\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2} [AP]M', text)
    if match:
        return match.group(0)
    else:
        return "Unknown date"

# Helper function to determine the vote type based on URL and response text
def determine_vote_type(vote_url, response_text):
    if "mtgvotes.jsp" in vote_url:
        return "Committee Vote"
    elif "house=H" in vote_url:
        return "House Vote"
    elif "house=S" in vote_url:
        return "Senate Vote"
    if re.search(r'Voice vote', response_text):
        if "house=H" in vote_url:
            return "House Voice Vote"
        elif "house=S" in vote_url:
            return "Senate Voice Vote"
    return "Unknown Vote"

# Safely converts vote count strings to integers, handling 'N/A' or invalid values
def safe_int_conversion(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0

# Finds the vote URLs on the bill page
def find_vote_pages(year, bill_number):
    url = f"https://le.utah.gov/~{year}/bills/static/{bill_number}.html"
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Failed to retrieve bill page for {bill_number} in {year}. Status code: {response.status_code}")
        return []
    
    vote_urls = re.findall(r'/(DynaBill/svotes\.jsp|DynaBill/mtgvotes\.jsp)\?[^\'"<>]+', response.text)
    full_vote_urls = [f"https://le.utah.gov/{url}" for url in vote_urls]
    return full_vote_urls

# Extracts and tallies votes from each vote page
def extract_votes_from_vote_page(vote_url):
    response = requests.get(vote_url)
    if response.status_code != 200:
        print(f"Failed to retrieve vote page {vote_url}. Status code: {response.status_code}")
        return None, None, None, None

    vote_date = extract_vote_date(response.text)
    vote_type = determine_vote_type(vote_url, response.text)

    # For committee votes, handle mtgvotes.jsp
    if "mtgvotes.jsp" in vote_url:
        yeas_match = re.search(r'Yeas - (\d+)', response.text)
        nays_match = re.search(r'Nays - (\d+)', response.text)
        absent_match = re.search(r'Absent or not voting - (\d+)', response.text)
        
        yeas = safe_int_conversion(yeas_match.group(1)) if yeas_match else 0
        nays = safe_int_conversion(nays_match.group(1)) if nays_match else 0
        absent = safe_int_conversion(absent_match.group(1)) if absent_match else 0
        
        yeas_reps = re.findall(r'<a[^>]+>(.*?)<\/a>', re.search(r'Yeas - \d+.*?<table>(.*?)<\/table>', response.text, re.DOTALL).group(1))
        nays_reps = re.findall(r'<a[^>]+>(.*?)<\/a>', re.search(r'Nays - \d+.*?<table>(.*?)<\/table>', response.text, re.DOTALL).group(1)) if nays_match else []
        absent_reps = re.findall(r'<a[^>]+>(.*?)<\/a>', re.search(r'Absent or not voting - \d+.*?<table>(.*?)<\/table>', response.text, re.DOTALL).group(1)) if absent_match else []
        
        return yeas, nays, absent, yeas_reps, nays_reps, absent_reps, vote_date, vote_type

    # For House/Senate votes (svotes.jsp)
    yeas_match = re.search(r'Yeas - (\d+)', response.text)
    nays_match = re.search(r'Nays - (\d+)', response.text)
    absent_match = re.search(r'Absent or not voting - (\d+)', response.text)

    yeas = safe_int_conversion(yeas_match.group(1)) if yeas_match else 0
    nays = safe_int_conversion(nays_match.group(1)) if nays_match else 0
    absent = safe_int_conversion(absent_match.group(1)) if absent_match else 0

    yeas_section = re.search(r'Yeas - \d+.*?<table>(.*?)<\/table>', response.text, re.DOTALL)
    yeas_reps = re.findall(r'<a[^>]+>(.*?)<\/a>', yeas_section.group(1)) if yeas_section else []

    nays_section = re.search(r'Nays - \d+.*?<table>(.*?)<\/table>', response.text, re.DOTALL)
    nays_reps = re.findall(r'<a[^>]+>(.*?)<\/a>', nays_section.group(1)) if nays_section else []

    absent_section = re.search(r'Absent or not voting - \d+.*?<table>(.*?)<\/table>', response.text, re.DOTALL)
    absent_reps = re.findall(r'<a[^>]+>(.*?)<\/a>', absent_section.group(1)) if absent_section else []

    return yeas, nays, absent, yeas_reps, nays_reps, absent_reps, vote_date, vote_type

# Main function to scrape voting data for a specific year and bill
def vote_scrape(year, bill_number):
    vote_pages = find_vote_pages(year, bill_number)

    if not vote_pages:
        print(f"No vote pages found for {bill_number} in {year}.")
        return

    for vote_url in vote_pages:
        yeas, nays, absent, yeas_reps, nays_reps, absent_reps, vote_date, vote_type = extract_votes_from_vote_page(vote_url)
        print(f"Vote Type: {vote_type}")
        print(f"Vote Date: {vote_date}")
        print(f"Yeas: {yeas}, Nays: {nays}, Absent: {absent}")
        print(f"Yea Votes: {yeas_reps}")
        print(f"Nay Votes: {nays_reps}")
        print(f"Absent Votes: {absent_reps}")
        print("------------")

if __name__ == '__main__':
    year = 2024
    bill_number = "HB0001"
    vote_scrape(year, bill_number)