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
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "https://annas-archive.org"

load_dotenv()

DEFAULT_SEARCH_PARAMS = {
    'index': '',
    'page': '1',
    'q': '',
    'display': '',
    'sort': '',
    
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
    
    'ext': [
        'anti__pdf',   # Exclude PDF
        'epub',        # Include EPUB
        'anti__mobi',  # Exclude MOBI
        'anti__fb2',   # Exclude FB2
        'anti__cbr'    # Exclude CBR
    ],
    
    'acc': [
        'aa_download',                      # Include direct downloads
        'anti__external_download',          # Exclude external downloads
        'anti__external_borrow',            # Exclude external borrows
        'anti__external_borrow_printdisabled', # Exclude print-disabled borrows
        'anti__torrents_available'          # Exclude torrents
    ],
    
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

def construct_search_url(query):
    """Construct the search URL for a given query using the defined search parameters."""
    params = DEFAULT_SEARCH_PARAMS.copy()
    params['q'] = query
    
    query_parts = []
    for key, value in params.items():
        if isinstance(value, list):
            for item in value:
                query_parts.append(f"{key}={item}")
        else:
            query_parts.append(f"{key}={value}")
    
    query_string = "&".join(query_parts)
    return f"{BASE_URL}/search?{query_string}"

def extract_search_results(html_content):
    """Parse the search results HTML and extract book links with metadata."""
    # Remove HTML comments that hide lazy-loaded content
    html_content = html_content.replace("<!--", "").replace("-->", "")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    books = []
    
    # Check if there are partial matches indicated in the results
    partial_matches_count = None
    partial_matches_text = soup.select_one("div.italic.mt-2")
    if partial_matches_text and "partial matches" in partial_matches_text.text:
        count_text = partial_matches_text.text.strip()
        try:
            partial_matches_count = int(count_text.split()[0])
            logger.info(f"Found {partial_matches_count} partial matches")
        except (ValueError, IndexError):
            pass
    
    # Find all book links with MD5 hashes
    book_links = soup.select('a[href^="/md5/"]')
    logger.info(f"Found {len(book_links)} total search results after uncommenting")
    
    # Process each book link to extract information
    for i, link in enumerate(book_links):
        href = link.get('href', '')
        all_text = link.get_text(separator=' ', strip=True)
        
        # Determine format priority based on file type
        format_priority = 0
        if 'epub' in all_text.lower():
            format_priority = 3  # Highest priority
        elif 'pdf' in all_text.lower():
            format_priority = 2  # Medium priority
        elif 'mobi' in all_text.lower():
            format_priority = 1  # Lower priority
        
        # Skip unsupported formats
        if format_priority == 0:
            logger.info(f"Skipping unsupported format in result {i+1}")
            continue
            
        # Set human-readable format type
        format_type = "Unknown"
        if format_priority == 3:
            format_type = "EPUB"
        elif format_priority == 2:
            format_type = "PDF"
        elif format_priority == 1:
            format_type = "MOBI"
        
        logger.info(f"Found {format_type} result {i+1}: {href}")
        
        # Extract book metadata from the link
        title = "Unknown Title"
        title_elem = link.select_one('h3')
        if title_elem:
            title = title_elem.text.strip()
        
        author = "Unknown Author"
        author_elem = link.select_one('div.italic')
        if author_elem:
            author = author_elem.text.strip()
        
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
            'original_index': i,
            'is_partial_match': partial_matches_count is not None
        }
        
        books.append(book_info)
    
    # Sort results by format priority (highest first), then by original order
    books.sort(key=lambda x: (-x['format_priority'], x['original_index']))
    
    logger.info(f"Found {len(books)} acceptable format results after filtering")
    return books

def display_selection_menu(books):
    """Display an interactive selection menu for the user to choose a book."""
    if not books:
        return None
    
    if len(books) == 1:
        print(f"Only one result found: {books[0]['title']}")
        return 0
    
    epub_count = sum(1 for book in books if book['format_priority'] == 3)
    pdf_count = sum(1 for book in books if book['format_priority'] == 2)
    mobi_count = sum(1 for book in books if book['format_priority'] == 1)
    
    print(f"\nFound {len(books)} results ({epub_count} EPUB, {pdf_count} PDF, {mobi_count} MOBI):")
    
    choices = []
    for i, book in enumerate(books):
        size = "Unknown size"
        if book['format'] and "MB" in book['format']:
            size_match = re.search(r'(\d+\.\d+)MB', book['format'])
            if size_match:
                size = f"{size_match.group(1)}MB"
        
        display_name = f"{book['title']} by {book['author']}"
        
        format_icon = "📄"  # Default
        if book['format_priority'] == 3:
            format_icon = "📙"  # EPUB
        elif book['format_priority'] == 2:
            format_icon = "📑"  # PDF
        elif book['format_priority'] == 1:
            format_icon = "📕"  # MOBI
        
        details = f"\n   {format_icon} Format: {book['format']}\n   Size: {size}"
        
        choices.append(Choice(value=i, name=f"{display_name}{details}"))
    
    choices.append(Choice(value=None, name="Cancel download"))
    
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
    """Extract the first "fast download" link from the book page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    download_links = soup.select('a[href^="/fast_download/"]')
    
    for link in download_links:
        if 'fast' in link.text.lower():
            return link['href']
    
    if download_links:
        return download_links[0]['href']
    
    return None

def download_file(session, url, output_path, format_priority=None):
    """Download a file with progress reporting."""
    response = session.get(url, stream=True)
    response.raise_for_status()
    
    content_type = response.headers.get('content-type', '').lower()
    
    expected_format = None
    if format_priority == 3:
        expected_format = "epub"
    elif format_priority == 2:
        expected_format = "pdf"
    elif format_priority == 1:
        expected_format = "mobi"
    
    if expected_format and expected_format not in content_type and 'octet-stream' not in content_type:
        content_disp = response.headers.get('content-disposition', '').lower()
        if expected_format not in content_disp and 'filename=' in content_disp:
            logger.warning(f"Content may not match expected format {expected_format}: {content_type}")
    
    total_size = int(response.headers.get('content-length', 0))
    
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    downloaded = 0
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\rDownloading: {downloaded/1024/1024:.1f}MB of {total_size/1024/1024:.1f}MB ({percent:.1f}%)", end='')
    
    print()
    return True

def get_filename_from_headers(headers, format_priority=None):
    """Extract filename from Content-Disposition header."""
    if 'content-disposition' in headers:
        match = re.search(r'filename="?([^"]+)"?', headers['content-disposition'])
        if match:
            filename = match.group(1)
            
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
    """Clean a string to make it suitable for a filename."""
    return re.sub(r'[\\/*?:"<>|]', '', text)

def download_book_by_query(query, output_dir, interactive=False):
    """Main function to download a book by search query."""
    # Set up session with user agent and authentication
    session = requests.Session()
    
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
    })
    
    account_id = os.getenv('AA_ACCOUNT_ID')
    if account_id:
        session.cookies.set('aa_account_id2', account_id)
        logger.info("Using account ID from environment for authentication")
    else:
        logger.warning("No account ID found in .env file - some results may be limited")
    
    # Search for books matching query
    search_url = construct_search_url(query)
    logger.info(f"Searching for query: {query}")
    logger.info(f"URL: {search_url}")
    
    try:
        response = session.get(search_url)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Search request failed: {e}")
        return False
    
    books = extract_search_results(response.text)
    if not books:
        logger.error("No acceptable format books found for this query")
        return False
    
    # Handle selection based on mode (interactive vs automatic)
    selected_book = None
    
    if interactive:
        selected_idx = display_selection_menu(books)
        if selected_idx is None:
            logger.info("User cancelled selection")
            return False
        selected_book = books[selected_idx]
    else:
        # For automatic mode, try to find the best match
        if len(books) == 1:
            selected_book = books[0]
        else:
            # Try to find an exact match in title or author
            for book in books:
                if query.lower() in book['title'].lower() or query.lower() in book['author'].lower():
                    logger.info(f"Found exact query match: {book['title']}")
                    selected_book = book
                    break
            
            # If no exact match found, use the first result
            if not selected_book:
                logger.info(f"Using first result: {books[0]['title']}")
                selected_book = books[0]
    
    # Determine metadata about the selected book
    is_partial_match = selected_book.get('is_partial_match', False)
    match_type = "partial match" if is_partial_match else "direct match"
    
    format_type = "Unknown"
    if selected_book['format_priority'] == 3:
        format_type = "EPUB"
    elif selected_book['format_priority'] == 2:
        format_type = "PDF"
    elif selected_book['format_priority'] == 1:
        format_type = "MOBI"
    
    logger.info(f"Selected {format_type} book ({match_type}): {selected_book['title']} by {selected_book.get('author', 'Unknown')}")
    
    # Navigate to book page to find download link
    book_url = urljoin(BASE_URL, selected_book['link'])
    logger.info(f"Accessing book page: {book_url}")
    
    try:
        response = session.get(book_url)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Book page request failed: {e}")
        return False
    
    download_link = extract_fast_download_link(response.text)
    if not download_link:
        logger.error("No download link found on the book page")
        return False
    
    # Start download process
    download_url = urljoin(BASE_URL, download_link)
    logger.info(f"Found download link: {download_url}")
    
    try:
        # Get file metadata before downloading
        response = session.head(download_url)
        response.raise_for_status()
        
        # Determine filename, either from headers or construct from book info
        filename = get_filename_from_headers(response.headers, selected_book['format_priority'])
        if not filename:
            title = clean_filename(selected_book['title'])
            author = clean_filename(selected_book.get('author', 'Unknown'))
            
            extension = ".epub"
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

def interactive_mode(output_dir, verbose):
    """Run the downloader in interactive mode, allowing for multiple queries to be processed."""
    # Configure logging based on verbosity
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    # Display welcome message and instructions
    print("\n=== Anna's Archive Interactive Downloader ===")
    print(f"Output directory: {output_dir}")
    print("Enter search queries one at a time. Type 'exit', 'quit', or press Ctrl+C to exit.")
    print("You can also paste multiple queries (one per line).")
    print("When multiple books are found, you'll get a selection menu.")
    print("=========================================\n")
    
    # Set up session with user agent and authentication
    session = requests.Session()
    
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
    })
    
    account_id = os.getenv('AA_ACCOUNT_ID')
    if account_id:
        session.cookies.set('aa_account_id2', account_id)
        logger.info("Using account ID from environment for authentication")
    else:
        logger.warning("No account ID found in .env file - some results may be limited")
    
    # Main interactive loop
    try:
        while True:
            query_input = input("\nEnter search query (or 'quit' to exit): ").strip()
            
            if query_input.lower() in ['exit', 'quit', 'q']:
                print("Exiting...")
                break
            
            # Handle case where user pastes multiple queries at once
            queries = [query.strip() for query in query_input.split('\n') if query.strip()]
            
            for query in queries:
                print(f"\nProcessing query: {query}")
                
                # Search for books matching query
                search_url = construct_search_url(query)
                logger.info(f"URL: {search_url}")
                
                try:
                    response = session.get(search_url)
                    response.raise_for_status()
                except requests.RequestException as e:
                    logger.error(f"Search request failed: {e}")
                    print(f"❌ Search failed for query: {query}")
                    continue
                
                books = extract_search_results(response.text)
                
                if not books:
                    print(f"❌ No books found for query: {query}")
                    continue
                
                # Let user select which book to download
                selected_idx = display_selection_menu(books)
                if selected_idx is None:
                    print(f"Download cancelled for query: {query}")
                    continue
                
                selected_book = books[selected_idx]
                print(f"Selected: {selected_book['title']} by {selected_book.get('author', 'Unknown')}")
                
                # Navigate to book page to find download link
                book_url = urljoin(BASE_URL, selected_book['link'])
                logger.info(f"Accessing book page: {book_url}")
                
                try:
                    response = session.get(book_url)
                    response.raise_for_status()
                except requests.RequestException as e:
                    logger.error(f"Book page request failed: {e}")
                    print(f"❌ Failed to access book page for query: {query}")
                    continue
                
                download_link = extract_fast_download_link(response.text)
                if not download_link:
                    print("❌ No download link found on the book page")
                    continue
                
                # Start download process
                download_url = urljoin(BASE_URL, download_link)
                logger.info(f"Found download link: {download_url}")
                
                try:
                    # Get file metadata before downloading
                    response = session.head(download_url)
                    response.raise_for_status()
                    
                    # Determine filename, either from headers or construct from book info
                    filename = get_filename_from_headers(response.headers, selected_book['format_priority'])
                    if not filename:
                        title = clean_filename(selected_book['title'])
                        author = clean_filename(selected_book.get('author', 'Unknown'))
                        
                        extension = ".epub"
                        if selected_book['format_priority'] == 2:
                            extension = ".pdf"
                        elif selected_book['format_priority'] == 1:
                            extension = ".mobi"
                        
                        filename = f"{title} - {author}{extension}"
                    
                    output_path = os.path.join(output_dir, filename)
                    
                    # Download the actual file
                    print(f"Downloading to: {output_path}")
                    download_success = download_file(session, download_url, output_path, selected_book['format_priority'])
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

def debug_search(query, output_dir, verbose=False):
    """Debug function to just search and print results without downloading."""
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    session = requests.Session()
    
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
    })
    
    account_id = os.getenv('AA_ACCOUNT_ID')
    if account_id:
        session.cookies.set('aa_account_id2', account_id)
        logger.info("Using account ID from environment for authentication")
    else:
        logger.warning("No account ID found in .env file - some results may be limited")
    
    search_url = construct_search_url(query)
    logger.info(f"Searching for query: {query}")
    logger.info(f"URL: {search_url}")
    
    try:
        response = session.get(search_url)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Search request failed: {e}")
        return 1
    
    debug_file = os.path.join(output_dir, "results.html")
    with open(debug_file, "w", encoding="utf-8") as f:
        f.write(response.text)
    logger.info(f"Saved full HTML response to {debug_file}")
    
    md5_count = response.text.count('href="/md5/')
    logger.info(f"Direct count of 'href=\"/md5/' in HTML: {md5_count}")
    
    books = extract_search_results(response.text)
    
    print("\n===== DEBUG SEARCH RESULTS =====")
    print(f"Query: {query}")
    print(f"Total results found: {len(books)}")
    print(f"Raw MD5 link count in HTML: {md5_count}")
    
    for i, book in enumerate(books):
        print(f"\nResult {i+1}:")
        print(f"  Title: {book['title']}")
        print(f"  Author: {book['author']}")
        print(f"  Format: {book['format']}")
        print(f"  Link: {book['link']}")
        print(f"  Partial Match: {book['is_partial_match']}")
    
    return 0

def main():
    """Main entry point for the script."""
    # Get default output directory from environment or use 'books/'
    default_output_dir = os.getenv('OUTPUT_DIR', 'books/')
    
    # Set up command line argument parser
    parser = argparse.ArgumentParser(description='Download books from Anna\'s Archive by search query')
    
    # Create subparsers for different operation modes
    subparsers = parser.add_subparsers(dest='mode', help='Operation mode')
    
    # Single download mode
    single_parser = subparsers.add_parser('single', help='Download a single book')
    single_parser.add_argument('query', help='Search query (title, author, ISBN, etc.)')
    single_parser.add_argument('--interactive', '-i', action='store_true', help='Display selection menu for multiple results')
    
    # Interactive mode for multiple downloads
    interactive_parser = subparsers.add_parser('interactive', help='Run in interactive mode to download multiple books')
    
    # Debug mode for troubleshooting
    debug_parser = subparsers.add_parser('debug', help='Debug search results without downloading')
    debug_parser.add_argument('query', help='Search query to debug')
    
    # Add common arguments to all modes
    for subparser in [single_parser, interactive_parser, debug_parser]:
        subparser.add_argument('--output', '-o', default=default_output_dir, help='Directory to save downloaded books')
        subparser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Show help if no mode specified
    if not args.mode:
        parser.print_help()
        return 1
    
    # Configure logging based on verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # Run the appropriate mode
    if args.mode == 'single':
        success = download_book_by_query(args.query, args.output, args.interactive)
        return 0 if success else 1
    elif args.mode == 'interactive':
        return interactive_mode(args.output, args.verbose)
    elif args.mode == 'debug':
        return debug_search(args.query, args.output, args.verbose)
    
    return 0

if __name__ == "__main__":
    main()