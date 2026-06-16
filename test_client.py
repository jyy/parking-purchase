import urllib.request
import urllib.error
import argparse

def test_endpoint(client_id, client_secret):
    url = "https://park.onesixtwelve.com/?action=buy&when=tomorrow"
    
    print(f"Sending request to {url}...")
    req = urllib.request.Request(url)
    req.add_header("CF-Access-Client-Id", client_id)
    req.add_header("CF-Access-Client-Secret", client_secret)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

    try:
        with urllib.request.urlopen(req) as response:
            print("✅ SUCCESS!")
            print(f"Status Code: {response.getcode()}")
            print(f"Response Body: {response.read().decode('utf-8')}")
    except urllib.error.HTTPError as e:
        print("❌ FAILED - Access Denied or Server Error")
        print(f"HTTP Error: {e.code}")
        try:
            error_body = e.read().decode('utf-8')
            print("\n--- ERROR RESPONSE BODY ---")
            # Print first 500 characters of the error body to keep it clean
            print(error_body[:500])
            print("---------------------------\n")
            if "cloudflare-access" in error_body.lower() or "cf-access" in error_body.lower():
                print("Diagnose: Cloudflare Access is specifically rejecting this (Policy or Token issue).")
            else:
                print("Diagnose: This might be Cloudflare's Web Application Firewall (WAF) blocking the Python script due to its User-Agent, rather than a token issue.")
        except:
            pass
        print("This usually means the Service Token is incorrect, or the Policy wasn't applied correctly in Cloudflare.")
    except urllib.error.URLError as e:
        print("❌ FAILED - Connection Error")
        print(f"URL Error: {e.reason}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Cloudflare Access Service Token")
    parser.add_argument("--id", required=True, help="CF-Access-Client-Id")
    parser.add_argument("--secret", required=True, help="CF-Access-Client-Secret")
    args = parser.parse_args()
    
    test_endpoint(args.id, args.secret)
