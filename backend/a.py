# from playwright.sync_api import sync_playwright

# with sync_playwright() as p:
#     browser = p.chromium.launch(headless=False)  # launches Chromium
#     page = browser.new_page()
#     page.goto("https://flipkart.com")
#     print(page.title())
#     browser.close()
import csv

input_file = r"C:\Users\Webrebate\Downloads\kanu.csv"
output_file = r"C:\Users\Webrebate\Downloads\kanu_fixed.csv"

with open(input_file, newline='', encoding='utf-8') as infile, \
     open(output_file, 'w', newline='', encoding='utf-8') as outfile:

    # Detect tab-delimited file
    reader = csv.DictReader(infile, delimiter='\t')
    writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames, delimiter=',', quoting=csv.QUOTE_ALL)
    writer.writeheader()

    for row in reader:
        # Escape quotes in cookies JSON
        if 'cookies' in row and row['cookies']:
            row['cookies'] = row['cookies'].replace('"', '""')
        writer.writerow(row)

print("CSV fixed:", output_file)
