import requests
from bs4 import BeautifulSoup
import argparse
import json
import os
import re
import logging
from urllib.parse import urljoin
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base URL for Anna's Archive
BASE_URL = "https://annas-archive.org"

def load_auth_headers(headers_file):
    """
    Load authentication headers from a JSON file.
    """
    try:
        with open(headers_file, 'r') as f:
            headers = json.load(f)
            logger.info(f"Loaded authentication headers from {headers_file}")
            return headers
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error loading headers file: {e}")
        return None

def extract_auth_from_curl(curl_command):
    """
    Extract headers and cookies from a curl command string.
    """
    headers = {}
    cookies = {}
    
    # Extract headers
    header_matches = re.findall(r'-H\s+[\'"](.+?)[\'"]', curl_command)
    for header in header_matches:
        if ':' in header:
            key, value = header.split(':', 1)
            headers[key.strip()] = value.strip()
    
    # Extract cookies
    cookie_matches = re.findall(r'-b\s+[\'"](.+?)[\'"]', curl_command)
    for cookie_str in cookie_matches:
        for cookie_pair in cookie_str.split(';'):
            if '=' in cookie_pair:
                key, value = cookie_pair.strip().split('=', 1)
                cookies[key] = value
    
    return headers, cookies

# Default search parameters
DEFAULT_SEARCH_PARAMS = {
    # Basic search parameters
    'index': '',
    'page': '1',
    'q': '',  # Will be set to ISBN
    'display': '',
    'sort': '',
    
    # Content type parameters
    'content': [
        'anti__book_nonfiction',  # Exclude non-fiction
        'book_fiction',           # Include fiction
        'anti__book_unknown',     # Exclude unknown
        'anti__magazine',         # Exclude magazines
        'anti__book_comic',       # Exclude comics
        'anti__standards_document', # Exclude standards docs
        'anti__other',            # Exclude other content types
        'anti__musical_score'     # Exclude musical scores
    ],
    
    # File format parameters
    'ext': [
        'anti__pdf',   # Exclude PDF
        'epub',        # Include EPUB
        'anti__mobi',  # Exclude MOBI
        'anti__fb2',   # Exclude FB2
        'anti__cbr'    # Exclude CBR
    ],
    
    # Access type parameters  
    'acc': [
        'aa_download',                      # Include direct downloads
        'anti__external_download',          # Exclude external downloads
        'anti__external_borrow',            # Exclude external borrows
        'anti__external_borrow_printdisabled', # Exclude print-disabled borrows
        'anti__torrents_available'          # Exclude torrents
    ],
    
    # Language parameters
    'lang': [
        'en',          # Include English
        'anti__zh',    # Exclude Chinese
        'anti__ru',    # Exclude Russian
        'anti__es',    # Exclude Spanish
        'anti__fr',    # Exclude French
        'anti__de',    # Exclude German
        'anti__it',    # Exclude Italian
        'anti__pt',    # Exclude Portuguese
        'anti__pl',    # Exclude Polish
        'anti__nl'     # Exclude Dutch
    ]
}

def construct_search_url(isbn):
    """
    Construct the search URL for a given ISBN using the defined search parameters.
    """
    # Create a copy of the default params
    params = DEFAULT_SEARCH_PARAMS.copy()
    
    # Set the ISBN as the query parameter
    params['q'] = isbn
    
    # Build the query string
    query_parts = []
    
    for key, value in params.items():
        if isinstance(value, list):
            # Handle multi-value parameters (content, ext, acc, lang)
            for item in value:
                query_parts.append(f"{key}={item}")
        else:
            # Handle single-value parameters
            query_parts.append(f"{key}={value}")
    
    # Join all parts with & and append to base URL
    query_string = "&".join(query_parts)
    return f"{BASE_URL}/search?{query_string}"

def extract_search_results(html_content):
    """
    Parse the search results HTML and extract book links with metadata.
    Includes both direct matches and partial matches, allowing EPUB, PDF, and MOBI formats.
    """
    # Pre-process the HTML to remove comment tags around lazy-loaded content
    html_content = html_content.replace("<!--", "").replace("-->", "")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    books = []
    
    # Get count of partial matches if present
    partial_matches_count = None
    partial_matches_text = soup.select_one("div.italic.mt-2")
    if partial_matches_text and "partial matches" in partial_matches_text.text:
        count_text = partial_matches_text.text.strip()
        try:
            partial_matches_count = int(count_text.split()[0])
            logger.info(f"Found {partial_matches_count} partial matches")
        except (ValueError, IndexError):
            pass
    
    # Find all book links that match the MD5 pattern - in all sections, including partial matches
    book_links = soup.select('a[href^="/md5/"]')
    logger.info(f"Found {len(book_links)} total search results after uncommenting")
    
    # Debug: Log ALL links with their href values and extracted text
    for i, link in enumerate(book_links):
        href = link.get('href', '')
        
        # Get ALL text within the link element
        all_text = link.get_text(separator=' ', strip=True)
        
        # Determine format priority
        format_priority = 0  # Default/unknown
        if 'epub' in all_text.lower():
            format_priority = 3  # Highest priority
        elif 'pdf' in all_text.lower():
            format_priority = 2  # Medium priority
        elif 'mobi' in all_text.lower():
            format_priority = 1  # Lower priority
        
        # Skip if not one of our allowed formats
        if format_priority == 0:
            logger.info(f"Skipping unsupported format in result {i+1}")
            continue
            
        # Get format type for display
        format_type = "Unknown"
        if format_priority == 3:
            format_type = "EPUB"
        elif format_priority == 2:
            format_type = "PDF"
        elif format_priority == 1:
            format_type = "MOBI"
        
        logger.info(f"Found {format_type} result {i+1}: {href}")
        
        # Extract title
        title = "Unknown Title"
        title_elem = link.select_one('h3')
        if title_elem:
            title = title_elem.text.strip()
        
        # Extract author
        author = "Unknown Author"
        author_elem = link.select_one('div.italic')
        if author_elem:
            author = author_elem.text.strip()
        
        # Extract format for reference
        format_text = "Unknown format"
        format_elem = link.select_one('div[class*="text-gray-500"], div.text-gray-500, .text-gray-500')
        if format_elem:
            format_text = format_elem.text.strip()
        
        book_info = {
            'link': href,
            'title': title,
            'author': author,
            'format': format_text,
            'format_priority': format_priority,
            'original_index': i,  # Keep track of original ordering
            'is_partial_match': partial_matches_count is not None  # Flag if this is a partial match
        }
        
        books.append(book_info)
    
    # Sort results by format priority (highest first), then by original index to maintain original order
    books.sort(key=lambda x: (-x['format_priority'], x['original_index']))
    
    logger.info(f"Found {len(books)} acceptable format results after filtering")
    return books

def display_selection_menu(books):
    """
    Display an interactive selection menu for the user to choose a book.
    Returns the index of the selected book or None if cancelled.
    Uses InquirerPy for a keyboard-navigable interface.
    """
    if not books:
        return None
    
    # If there's only one result, return it without asking
    if len(books) == 1:
        print(f"Only one result found: {books[0]['title']}")
        return 0
    
    # Group results by format priority
    epub_count = sum(1 for book in books if book['format_priority'] == 3)
    pdf_count = sum(1 for book in books if book['format_priority'] == 2)
    mobi_count = sum(1 for book in books if book['format_priority'] == 1)
    
    print(f"\nFound {len(books)} results ({epub_count} EPUB, {pdf_count} PDF, {mobi_count} MOBI):")
    
    # Create choices for the menu
    choices = []
    for i, book in enumerate(books):
        # Extract size if available in the format text
        size = "Unknown size"
        if book['format'] and "MB" in book['format']:
            size_match = re.search(r'(\d+\.\d+)MB', book['format'])
            if size_match:
                size = f"{size_match.group(1)}MB"
        
        # Format a clean display name
        display_name = f"{book['title']} by {book['author']}"
        
        # Get format type icon
        format_icon = "📄"  # Default
        if book['format_priority'] == 3:
            format_icon = "📙"  # EPUB
        elif book['format_priority'] == 2:
            format_icon = "📑"  # PDF
        elif book['format_priority'] == 1:
            format_icon = "📕"  # MOBI
        
        # Create a more detailed entry for the menu
        details = f"\n   {format_icon} Format: {book['format']}\n   Size: {size}"
        
        # Add to choices with the index as the value
        choices.append(Choice(value=i, name=f"{display_name}{details}"))
    
    # Add a cancel option
    choices.append(Choice(value=None, name="Cancel download"))
    
    # Display the interactive menu
    result = inquirer.select(
        message="Select a book to download:",
        choices=choices,
        default=0,
        qmark="📚",
        amark="✓",
        instruction="(Use arrow keys to navigate, Enter to select)"
    ).execute()
    
    return result

def extract_fast_download_link(html_content):
    """
    Extract the first "fast download" link from the book page.
    No longer filtering by EPUB only, as we support multiple formats.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Look for links with "fast" in the text
    download_links = soup.select('a[href^="/fast_download/"]')
    
    for link in download_links:
        if 'fast' in link.text.lower():
            return link['href']
    
    # If no specific "fast" link found, return the first download link if available
    if download_links:
        return download_links[0]['href']
    
    return None

def download_file(session, url, output_path, format_priority=None):
    """
    Download a file with progress reporting.
    """
    response = session.get(url, stream=True)
    response.raise_for_status()
    
    # Check for content type to ensure it matches expected format
    content_type = response.headers.get('content-type', '').lower()
    
    # Get expected format from priority
    expected_format = None
    if format_priority == 3:
        expected_format = "epub"
    elif format_priority == 2:
        expected_format = "pdf"
    elif format_priority == 1:
        expected_format = "mobi"
    
    # If we have an expected format, verify content matches (loosely)
    if expected_format and expected_format not in content_type and 'octet-stream' not in content_type:
        # Check with content-disposition as well
        content_disp = response.headers.get('content-disposition', '').lower()
        if expected_format not in content_disp and 'filename=' in content_disp:
            logger.warning(f"Content may not match expected format {expected_format}: {content_type}")
    
    # Get total file size if available
    total_size = int(response.headers.get('content-length', 0))
    
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # Download the file
    downloaded = 0
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                
                # Report progress for large files
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\rDownloading: {downloaded/1024/1024:.1f}MB of {total_size/1024/1024:.1f}MB ({percent:.1f}%)", end='')
    
    print()  # New line after progress reporting
    return True

def get_filename_from_headers(headers, format_priority=None):
    """
    Extract filename from Content-Disposition header.
    Optionally enforce a specific extension based on format_priority.
    """
    if 'content-disposition' in headers:
        match = re.search(r'filename="?([^"]+)"?', headers['content-disposition'])
        if match:
            filename = match.group(1)
            
            # Optionally enforce extension based on format_priority
            if format_priority:
                base_name = os.path.splitext(filename)[0]
                if format_priority == 3:  # EPUB
                    filename = f"{base_name}.epub"
                elif format_priority == 2:  # PDF
                    filename = f"{base_name}.pdf"
                elif format_priority == 1:  # MOBI
                    filename = f"{base_name}.mobi"
                logger.info(f"Set filename extension based on format: {filename}")
                
            return filename
    return None

def clean_filename(text):
    """
    Clean a string to make it suitable for a filename.
    """
    return re.sub(r'[\\/*?:"<>|]', '', text)

def download_book_by_isbn(isbn, auth_file=None, curl_file=None, account_id=None, output_dir='.', interactive=False):
    """
    Main function to download a book by ISBN.
    If interactive=True, will display a selection menu instead of auto-selecting.
    """
    # Set up session with authentication
    session = requests.Session()
    
    # Add default headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
    })
    
    # Load authentication: direct account ID takes precedence
    if account_id:
        # Set the aa_account_id2 cookie directly
        session.cookies.set('aa_account_id2', account_id)
        logger.info("Using provided account ID for authentication")
    elif auth_file:
        headers = load_auth_headers(auth_file)
        if headers:
            session.headers.update(headers)
    elif curl_file:
        try:
            with open(curl_file, 'r') as f:
                curl_command = f.read()
            headers, cookies = extract_auth_from_curl(curl_command)
            session.headers.update(headers)
            
            # Add cookies to session
            for key, value in cookies.items():
                session.cookies.set(key, value)
            
            logger.info("Loaded authentication from curl command")
        except Exception as e:
            logger.error(f"Error loading curl file: {e}")
            return False
    
    # Step 1: Search for the book
    search_url = construct_search_url(isbn)
    logger.info(f"Searching for ISBN: {isbn}")
    logger.info(f"URL: {search_url}")
    
    try:
        response = session.get(search_url)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Search request failed: {e}")
        return False
    
    # Extract search results
    books = extract_search_results(response.text)
    if not books:
        logger.error("No acceptable format books found for this ISBN")
        return False
    
    # Select the book to download
    selected_book = None
    
    if interactive:
        # Interactive mode: let the user choose
        selected_idx = display_selection_menu(books)
        if selected_idx is None:
            logger.info("User cancelled selection")
            return False
        selected_book = books[selected_idx]
    else:
        # Auto-select mode: use our algorithm
        # Select first book if only one result
        if len(books) == 1:
            selected_book = books[0]
        else:
            # Try to find an exact ISBN match
            for book in books:
                if isbn in str(book):
                    logger.info(f"Found exact ISBN match: {book['title']}")
                    selected_book = book
                    break
            
            # If no exact match, use the first result
            if not selected_book:
                logger.info(f"Using first result: {books[0]['title']}")
                selected_book = books[0]
    
    is_partial_match = selected_book.get('is_partial_match', False)
    match_type = "partial match" if is_partial_match else "direct match"
    
    # Determine format type text
    format_type = "Unknown"
    if selected_book['format_priority'] == 3:
        format_type = "EPUB"
    elif selected_book['format_priority'] == 2:
        format_type = "PDF"
    elif selected_book['format_priority'] == 1:
        format_type = "MOBI"
    
    logger.info(f"Selected {format_type} book ({match_type}): {selected_book['title']} by {selected_book.get('author', 'Unknown')}")
    
    # Step 2: Go to the book page
    book_url = urljoin(BASE_URL, selected_book['link'])
    logger.info(f"Accessing book page: {book_url}")
    
    try:
        response = session.get(book_url)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Book page request failed: {e}")
        return False
    
    # Step 3: Extract the fast download link
    download_link = extract_fast_download_link(response.text)
    if not download_link:
        logger.error("No download link found on the book page")
        return False
    
    # Step 4: Download the book
    download_url = urljoin(BASE_URL, download_link)
    logger.info(f"Found download link: {download_url}")
    
    try:
        # Start the download
        response = session.head(download_url)  # Use HEAD to get headers without downloading
        response.raise_for_status()
        
        # Determine filename
        filename = get_filename_from_headers(response.headers, selected_book['format_priority'])
        if not filename:
            # Create filename from book info
            title = clean_filename(selected_book['title'])
            author = clean_filename(selected_book.get('author', 'Unknown'))
            
            # Add appropriate extension based on format
            extension = ".epub"  # Default
            if selected_book['format_priority'] == 2:
                extension = ".pdf"
            elif selected_book['format_priority'] == 1:
                extension = ".mobi"
            
            filename = f"{title} - {author}{extension}"
        
        output_path = os.path.join(output_dir, filename)
        logger.info(f"Downloading to: {output_path}")
        
        # Download the actual file
        download_success = download_file(session, download_url, output_path, selected_book['format_priority'])
        if download_success:
            logger.info(f"Successfully downloaded: {filename}")
            return True
        else:
            logger.error("Download failed")
            return False
            
    except requests.RequestException as e:
        logger.error(f"Download failed: {e}")
        return False

def interactive_mode(auth_file, curl_file, account_id, output_dir, verbose):
    """
    Run the downloader in interactive mode, allowing for multiple ISBNs to be processed.
    """
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    print("\n=== Anna's Archive Interactive Downloader ===")
    print(f"Output directory: {output_dir}")
    print("Enter ISBN numbers one at a time. Type 'exit', 'quit', or press Ctrl+C to exit.")
    print("You can also paste multiple ISBNs (one per line).")
    print("When multiple books are found, you'll get a selection menu.")
    print("=========================================\n")
    
    # Set up session with authentication
    session = requests.Session()
    
    # Add default headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
    })
    
    # Load authentication: direct account ID takes precedence
    if account_id:
        # Set the aa_account_id2 cookie directly
        session.cookies.set('aa_account_id2', account_id)
        logger.info("Using provided account ID for authentication")
    elif auth_file:
        headers = load_auth_headers(auth_file)
        if headers:
            session.headers.update(headers)
    elif curl_file:
        try:
            with open(curl_file, 'r') as f:
                curl_command = f.read()
            headers, cookies = extract_auth_from_curl(curl_command)
            session.headers.update(headers)
            
            # Add cookies to session
            for key, value in cookies.items():
                session.cookies.set(key, value)
            
            logger.info("Loaded authentication from curl command")
        except Exception as e:
            logger.error(f"Error loading curl file: {e}")
            return False
    
    try:
        while True:
            isbn_input = input("\nEnter ISBN (or 'quit' to exit): ").strip()
            
            if isbn_input.lower() in ['exit', 'quit', 'q']:
                print("Exiting...")
                break
            
            # Handle multiple ISBNs pasted at once (one per line)
            isbns = [isbn.strip() for isbn in isbn_input.split('\n') if isbn.strip()]
            
            for isbn in isbns:
                print(f"\nProcessing ISBN: {isbn}")
                
                # Step 1: Search for the book
                search_url = construct_search_url(isbn)
                logger.info(f"URL: {search_url}")
                
                try:
                    response = session.get(search_url)
                    response.raise_for_status()
                except requests.RequestException as e:
                    logger.error(f"Search request failed: {e}")
                    print(f"❌ Search failed for ISBN: {isbn}")
                    continue
                
                # Extract search results
                books = extract_search_results(response.text)
                
                if not books:
                    print(f"❌ No EPUB books found for ISBN: {isbn}")
                    continue
                
                # Display selection menu and get user's choice
                selected_idx = display_selection_menu(books)
                if selected_idx is None:
                    print(f"Download cancelled for ISBN: {isbn}")
                    continue
                
                selected_book = books[selected_idx]
                print(f"Selected: {selected_book['title']} by {selected_book.get('author', 'Unknown')}")
                
                # Step 2: Go to the book page
                book_url = urljoin(BASE_URL, selected_book['link'])
                logger.info(f"Accessing book page: {book_url}")
                
                try:
                    response = session.get(book_url)
                    response.raise_for_status()
                except requests.RequestException as e:
                    logger.error(f"Book page request failed: {e}")
                    print(f"❌ Failed to access book page for ISBN: {isbn}")
                    continue
                
                # Step 3: Extract the fast download link
                download_link = extract_fast_download_link(response.text)
                if not download_link:
                    print("❌ No download link found on the book page")
                    continue
                
                # Step 4: Download the book
                download_url = urljoin(BASE_URL, download_link)
                logger.info(f"Found download link: {download_url}")
                
                try:
                    # Start the download
                    response = session.head(download_url)  # Use HEAD to get headers without downloading
                    response.raise_for_status()
                    
                    # Determine filename
                    filename = get_filename_from_headers(response.headers)
                    if not filename:
                        # Create filename from book info
                        title = clean_filename(selected_book['title'])
                        author = clean_filename(selected_book.get('author', 'Unknown'))
                        
                        # Always use .epub extension
                        filename = f"{title} - {author}.epub"
                    
                    output_path = os.path.join(output_dir, filename)
                    
                    # Download the actual file
                    print(f"Downloading to: {output_path}")
                    download_success = download_file(session, download_url, output_path)
                    if download_success:
                        print(f"✅ Successfully downloaded: {filename}")
                    else:
                        print("❌ Download failed")
                        
                except requests.RequestException as e:
                    logger.error(f"Download failed: {e}")
                    print(f"❌ Download failed: {e}")
    
    except KeyboardInterrupt:
        print("\nExiting...")
    
    return 0

def main():
    parser = argparse.ArgumentParser(description='Download books from Anna\'s Archive by ISBN')
    
    # Create a subparser for different modes
    subparsers = parser.add_subparsers(dest='mode', help='Operation mode')
    
    # Single download mode
    single_parser = subparsers.add_parser('single', help='Download a single book')
    single_parser.add_argument('isbn', help='ISBN of the book to download')
    single_parser.add_argument('--interactive', '-i', action='store_true', help='Display selection menu for multiple results')
    
    # Interactive mode
    interactive_parser = subparsers.add_parser('interactive', help='Run in interactive mode to download multiple books')
    
    # Debug mode - just print search results without downloading
    debug_parser = subparsers.add_parser('debug', help='Debug search results without downloading')
    debug_parser.add_argument('isbn', help='ISBN to search for debugging')
    
    # Common arguments for all modes
    for subparser in [single_parser, interactive_parser, debug_parser]:
        auth_group = subparser.add_mutually_exclusive_group()
        auth_group.add_argument('--auth', help='Path to JSON file with authentication headers')
        auth_group.add_argument('--curl', help='Path to file containing curl command with authentication')
        auth_group.add_argument('--account-id', help='Anna\'s Archive account ID cookie value')
        
        subparser.add_argument('--output', '-o', default='.', help='Directory to save downloaded books')
        subparser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Default to interactive mode if no mode is specified
    if not args.mode:
        parser.print_help()
        return 1
    
    # Set logging level based on verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Run in the selected mode
    if args.mode == 'single':
        # Download a single book
        success = download_book_by_isbn(args.isbn, args.auth, args.curl, args.account_id, args.output, args.interactive)
        return 0 if success else 1
    elif args.mode == 'interactive':
        # Run in interactive mode
        return interactive_mode(args.auth, args.curl, args.account_id, args.output, args.verbose)
    elif args.mode == 'debug':
        # Run in debug mode - just search and print results
        return debug_search(args.isbn, args.auth, args.curl, args.account_id, args.verbose)
    
    return 0

def debug_search(isbn, auth_file=None, curl_file=None, account_id=None, verbose=False):
    """
    Debug function to just search and print results without downloading.
    """
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    # Set up session with authentication
    session = requests.Session()
    
    # Add default headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
    })
    
    # Load authentication
    if account_id:
        session.cookies.set('aa_account_id2', account_id)
    elif auth_file:
        headers = load_auth_headers(auth_file)
        if headers:
            session.headers.update(headers)
    elif curl_file:
        try:
            with open(curl_file, 'r') as f:
                curl_command = f.read()
            headers, cookies = extract_auth_from_curl(curl_command)
            session.headers.update(headers)
            for key, value in cookies.items():
                session.cookies.set(key, value)
        except Exception as e:
            logger.error(f"Error loading curl file: {e}")
            return 1
    
    # Search for the book
    search_url = construct_search_url(isbn)
    logger.info(f"Searching for ISBN: {isbn}")
    logger.info(f"URL: {search_url}")
    
    try:
        response = session.get(search_url)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Search request failed: {e}")
        return 1
    
    # Save the full HTML response for debugging
    with open(f"results.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    logger.info(f"Saved full HTML response to results.html")
    
    # Count MD5 links directly from the HTML to verify
    md5_count = response.text.count('href="/md5/')
    logger.info(f"Direct count of 'href=\"/md5/' in HTML: {md5_count}")
    
    # Extract search results
    books = extract_search_results(response.text)
    
    # Print results
    print("\n===== DEBUG SEARCH RESULTS =====")
    print(f"ISBN: {isbn}")
    print(f"Total EPUB results found: {len(books)}")
    print(f"Raw MD5 link count in HTML: {md5_count}")
    
    for i, book in enumerate(books):
        print(f"\nResult {i+1}:")
        print(f"  Title: {book['title']}")
        print(f"  Author: {book['author']}")
        print(f"  Format: {book['format']}")
        print(f"  Link: {book['link']}")
        print(f"  Partial Match: {book['is_partial_match']}")
    
    return 0

if __name__ == "__main__":
    main()