import requests
import json

def to_isbn10(isbn13):
    """Convert ISBN13 to ISBN10."""
    if not isbn13 or len(isbn13) != 13: return None
    body = isbn13[3:12]
    checksum = 0
    for i, digit in enumerate(body):
        checksum += int(digit) * (10 - i)
    remainder = checksum % 11
    check_digit = 11 - remainder
    if check_digit == 10: check_digit = 'X'
    elif check_digit == 11: check_digit = '0'
    else: check_digit = str(check_digit)
    return body + check_digit

def get_google_books_data(isbn):
    print(f"Testing Google Books for {isbn}...")
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        resp = requests.get(url)
        print(f"Google Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if "items" in data:
                info = data["items"][0].get("volumeInfo", {})
                return {
                    "title": info.get("title", ""),
                    "author": ", ".join(info.get("authors", [])),
                    "notes": info.get("description", ""),
                    "cover_url": info.get("imageLinks", {}).get("thumbnail", "")
                }
            else:
                print("Google: No items found")
    except Exception as e:
        print(f"Google Error: {e}")
    return None

def get_openbd_data(isbn):
    print(f"Testing OpenBD for {isbn}...")
    try:
        url = f"https://api.openbd.jp/v1/get?isbn={isbn}"
        resp = requests.get(url)
        print(f"OpenBD Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if data and data[0]:
                summary = data[0].get('summary', {})
                return {
                    "title": summary.get('title', ''),
                    "author": summary.get('author', ''),
                    "cover_url": summary.get('cover', '')
                }
            else:
                print("OpenBD: No data found")
    except Exception as e:
        print(f"OpenBD Error: {e}")
    return None

def test_isbn(isbn):
    print(f"\n--- Testing ISBN: {isbn} ---")
    
    # 1. Google
    g_data = get_google_books_data(isbn)
    print(f"Google Data: {g_data}")
    
    # 2. OpenBD
    o_data = get_openbd_data(isbn)
    print(f"OpenBD Data: {o_data}")
    
    # 3. Amazon
    isbn10 = to_isbn10(isbn)
    amz_url = f"http://images-amazon.com/images/P/{isbn10}.09.LZZZZZZZ.jpg"
    print(f"Amazon URL: {amz_url}")

if __name__ == "__main__":
    # Test with a known book (Zero to One)
    test_isbn("9784798132646") # Zero to One (Japanese)
    # Test with another technical book (Python)
    test_isbn("9784873119328") # O'Reilly Deep Learning
