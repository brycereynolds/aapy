import requests
from bs4 import BeautifulSoup
import argparse
import json
import os
import re
import sys
import copy
import logging
import time
from datetime import timedelta
from urllib.parse import urljoin
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from dotenv import load_dotenv
from threading import Thread
from requests.exceptions import RequestException, Timeout, ConnectionError
from contextlib import contextmanager
from colorama import init, Fore, Back, Style

# Initialize colorama for cross-platform colored terminal text
init(autoreset=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "https://annas-archive.org"

load_dotenv()

class ProgressIndicator:
    """Simple spinner animation for CLI to indicate ongoing operations."""
    
    def __init__(self, message):
        self.message = message
        self.running = False
        self.thread = None
        self.frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.index = 0
    
    def _spin(self):
        while self.running:
            frame = self.frames[self.index % len(self.frames)]
            sys.stdout.write(f"\r{self.message} {frame} ")
            sys.stdout.flush()
            self.index += 1
            time.sleep(0.1)
    
    def start(self):
        self.running = True
        self.thread = Thread(target=self._spin)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self, clear=True):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
        if clear:
            sys.stdout.write(f"\r{' ' * (len(self.message) + 10)}\r")
            sys.stdout.flush()

@contextmanager
def progress_spinner(message):
    """Context manager for showing a spinner during operations."""
    spinner = ProgressIndicator(message)
    spinner.start()
    try:
        yield
    finally:
        spinner.stop()

def robust_request(session, url, method="get", stream=False, timeout=(10, 60), retries=3, 
                  retry_delay=2, message="Processing request", show_spinner=True):
    """
    Makes a robust HTTP request with timeout, retries, and visual feedback.
    
    Args:
        session: requests.Session object to use
        url: URL to request
        method: HTTP method (get, head, post)
        stream: Whether to stream the response
        timeout: (connect_timeout, read_timeout) in seconds
        retries: Number of retry attempts
        retry_delay: Seconds to wait between retries
        message: Message to display during request
        show_spinner: Whether to show the spinner animation
    
    Returns:
        requests.Response object or None if all attempts fail
    """
    start_time = time.time()
    spinner = None
    
    if show_spinner:
        spinner = ProgressIndicator(message)
        spinner.start()
    
    for attempt in range(1, retries + 1):
        try:
            if spinner:
                spinner.message = f"{message} (attempt {attempt}/{retries})"
                
            if method.lower() == "get":
                response = session.get(url, stream=stream, timeout=timeout)
            elif method.lower() == "head":
                response = session.head(url, timeout=timeout)
            elif method.lower() == "post":
                response = session.post(url, stream=stream, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            elapsed = time.time() - start_time
            
            if spinner:
                spinner.stop()
                
            logger.info(f"Request completed in {elapsed:.2f}s")
            return response
            
        except Timeout as e:
            logger.warning(f"Request timeout (attempt {attempt}/{retries}): {e}")
            if attempt == retries:
                if spinner:
                    spinner.stop()
                logger.error(f"Failed after {retries} attempts due to timeout")
                return None
            time.sleep(retry_delay)
            
        except ConnectionError as e:
            logger.warning(f"Connection error (attempt {attempt}/{retries}): {e}")
            if attempt == retries:
                if spinner:
                    spinner.stop()
                logger.error(f"Failed after {retries} attempts due to connection error")
                return None
            time.sleep(retry_delay)
            
        except RequestException as e:
            logger.warning(f"Request error (attempt {attempt}/{retries}): {e}")
            if attempt == retries:
                if spinner:
                    spinner.stop()
                logger.error(f"Failed after {retries} attempts due to request error")
                return None
            time.sleep(retry_delay)
    
    if spinner:
        spinner.stop()
    return None

def load_config(config_path="config.json"):
    """Load configuration from a JSON file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Validate required configuration sections
        required_sections = ['search', 'content', 'formats', 'access', 'languages']
        for section in required_sections:
            if section not in config:
                logger.error(f"Missing required config section: {section}")
                sys.exit(1)
                
        # Validate format definitions
        if 'definitions' not in config['formats']:
            logger.error("Missing format definitions in config")
            sys.exit(1)
            
        return config
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in config file: {config_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading config file: {e}")
        sys.exit(1)

def generate_search_params(config, query=""):
    """Generate search parameters based on configuration."""
    params = {
        'index': config['search'].get('index', ''),
        'page': config['search'].get('page', '1'),
        'q': query,
        'display': config['search'].get('display', ''),
        'sort': config['search'].get('sort', ''),
        'content': [],
        'ext': [],
        'acc': [],
        'lang': []
    }
    
    # Process content types
    content_types = config['content'].get('types', [])
    content_ignore = config['content'].get('ignore', [])
    
    for item in content_types:
        if item not in content_ignore:
            params['content'].append(item)
        else:
            params['content'].append(f"anti__{item}")
    
    # Process formats
    format_keys = list(config['formats']['definitions'].keys())
    format_ignore = config['formats'].get('ignore', [])
    
    for item in format_keys:
        if item not in format_ignore:
            params['ext'].append(item)
        else:
            params['ext'].append(f"anti__{item}")
    
    # Process access options
    access_types = config['access'].get('types', [])
    access_ignore = config['access'].get('ignore', [])
    
    for item in access_types:
        if item not in access_ignore:
            params['acc'].append(item)
        else:
            params['acc'].append(f"anti__{item}")
    
    # Process languages
    lang_types = config['languages'].get('types', [])
    lang_ignore = config['languages'].get('ignore', [])
    
    for item in lang_types:
        if item not in lang_ignore:
            params['lang'].append(item)
        else:
            params['lang'].append(f"anti__{item}")
    
    return params

def apply_command_line_overrides(config, args):
    """Apply command-line argument overrides to the config."""
    cfg = copy.deepcopy(config)
    
    # Apply format overrides
    if hasattr(args, 'formats') and args.formats:
        # Get all format keys from definitions
        all_formats = list(cfg['formats']['definitions'].keys())
        # Set ignore list to all formats that weren't specified
        cfg['formats']['ignore'] = [fmt for fmt in all_formats if fmt not in args.formats]
    
    # Apply content type overrides
    if hasattr(args, 'content') and args.content:
        all_content = cfg['content']['types']
        cfg['content']['ignore'] = [c for c in all_content if c not in args.content]
    
    # Apply access method overrides
    if hasattr(args, 'access') and args.access:
        all_access = cfg['access']['types']
        cfg['access']['ignore'] = [a for a in all_access if a not in args.access]
    
    # Apply language overrides
    if hasattr(args, 'languages') and args.languages:
        all_langs = cfg['languages']['types']
        cfg['languages']['ignore'] = [l for l in all_langs if l not in args.languages]
    
    # Apply output directory override
    if hasattr(args, 'output') and args.output:
        cfg['output_dir'] = args.output
    
    # Save color preference
    if hasattr(args, 'no_color'):
        cfg['use_colors'] = not args.no_color
    else:
        cfg['use_colors'] = True
    
    return cfg

def construct_search_url(query, config):
    """Construct the search URL for a given query using the configuration."""
    params = generate_search_params(config, query)
    
    query_parts = []
    for key, value in params.items():
        if isinstance(value, list):
            for item in value:
                query_parts.append(f"{key}={item}")
        else:
            if value:  # Only add non-empty values
                query_parts.append(f"{key}={value}")
    
    query_string = "&".join(query_parts)
    return f"{BASE_URL}/search?{query_string}"

def determine_format_type(text, config):
    """
    Determine the format type from text based on config definitions.
    Returns a tuple of (format_key, format_info) or (None, None) if not found.
    """
    text = text.lower()
    for format_key, format_info in config['formats']['definitions'].items():
        if format_key in text:
            return format_key, format_info
    return None, None

def extract_search_results(html_content, config):
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
        
        # Determine format based on text content
        format_key, format_info = determine_format_type(all_text, config)
        
        if not format_key:
            logger.info(f"Skipping unsupported format in result {i+1}")
            continue
        
        # Skip format if it's in the ignore list
        if format_key in config['formats'].get('ignore', []):
            logger.info(f"Skipping ignored format {format_key} in result {i+1}")
            continue
            
        # Get priority value from the configuration
        format_priority = format_info.get('priority', 0)
        
        logger.info(f"Found {format_info['display_name']} result {i+1}: {href}")
        
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
            'format_key': format_key,
            'format_info': format_info,
            'format_priority': format_priority,
            'original_index': i,
            'is_partial_match': partial_matches_count is not None
        }
        
        books.append(book_info)
    
    # Sort results by format priority (highest first), then by original order
    books.sort(key=lambda x: (-x['format_priority'], x['original_index']))
    
    logger.info(f"Found {len(books)} acceptable format results after filtering")
    return books

def display_selection_menu(books, config, use_colors=True):
    """Display an interactive selection menu for the user to choose a book."""
    if not books:
        return None
    
    # Count formats
    format_counts = {}
    for book in books:
        format_key = book['format_key']
        format_counts[format_key] = format_counts.get(format_key, 0) + 1
    
    # Create format count string with colors
    format_count_parts = []
    for format_key, count in format_counts.items():
        format_name = config['formats']['definitions'][format_key]['display_name']
        format_icon = config['formats']['definitions'][format_key]['icon']
        format_count_parts.append(
            f"{count} {format_icon} {format_name}"
        )
    
    format_count_str = ", ".join(format_count_parts)
    
    if len(books) == 1:
        print(f"\n{Style.BRIGHT}Found 1 result:{Style.RESET_ALL} {format_count_str}")
    else:
        print(f"\n{Style.BRIGHT}Found {len(books)} results:{Style.RESET_ALL} {format_count_str}")
    
    # For the actual menu, create choices with clear format/size info but without ANSI codes
    choices = []
    for i, book in enumerate(books):
        # Extract size information
        size = "Unknown size"
        if book['format'] and "MB" in book['format']:
            size_match = re.search(r'(\d+\.\d+)MB', book['format'])
            if size_match:
                size = f"{size_match.group(1)}MB"
        
        # Get format information
        format_icon = book['format_info']['icon']
        format_display = book['format_info']['display_name']
        
        # Create a prominently formatted display name
        display_name = f"[{i+1}] {book['title']} by {book['author']}\n   {format_icon} {format_display} | {size}"
        
        choices.append(Choice(value=i, name=display_name))
    
    choices.append(Choice(value=None, name="Cancel download"))
    
    result = inquirer.select(
        message="Select a book to download:",
        choices=choices,
        default=0,
        qmark="📚",
        amark="✅",
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

def download_file(session, url, output_path, format_info=None, use_colors=True):
    """Download a file with progress reporting."""
    if use_colors:
        print(f"\n{Fore.CYAN}Starting download...{Style.RESET_ALL}")
    else:
        print("\nStarting download...")
    response = robust_request(
        session, 
        url, 
        method="get", 
        stream=True, 
        message="Starting download",
        show_spinner=False
    )
    
    if not response:
        logger.error("Failed to start download - request failed")
        return False
    
    content_type = response.headers.get('content-type', '').lower()
    
    # Check if content type matches expected format
    if format_info and 'content_type' in format_info:
        expected_content_type = format_info['content_type']
        if expected_content_type not in content_type and 'octet-stream' not in content_type:
            content_disp = response.headers.get('content-disposition', '').lower()
            if expected_content_type not in content_disp and 'filename=' in content_disp:
                logger.warning(f"Content may not match expected format {format_info['display_name']}: {content_type}")
    
    total_size = int(response.headers.get('content-length', 0))
    
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    downloaded = 0
    start_time = time.time()
    last_update = start_time
    update_interval = 0.5  # Update progress every 0.5 seconds
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                
                current_time = time.time()
                if current_time - last_update > update_interval:
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        elapsed = current_time - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        
                        # Calculate ETA
                        if speed > 0 and total_size > downloaded:
                            eta_seconds = (total_size - downloaded) / speed
                            eta = str(timedelta(seconds=int(eta_seconds)))
                        else:
                            eta = "unknown"
                        
                    if use_colors:
                        print(f"\r{Fore.GREEN}Downloading: {Fore.CYAN}{downloaded/1024/1024:.1f}MB{Fore.RESET} of {Fore.CYAN}{total_size/1024/1024:.1f}MB {Fore.YELLOW}({percent:.1f}%){Fore.RESET} - {Fore.BLUE}{speed/1024/1024:.1f}MB/s{Fore.RESET} - ETA: {Fore.MAGENTA}{eta}{Style.RESET_ALL}", end='')
                    else:
                        print(f"\rDownloading: {downloaded/1024/1024:.1f}MB of {total_size/1024/1024:.1f}MB ({percent:.1f}%) - {speed/1024/1024:.1f}MB/s - ETA: {eta}", end='')
                    else:
                        if use_colors:
                            print(f"\r{Fore.GREEN}Downloading: {Fore.CYAN}{downloaded/1024/1024:.1f}MB{Style.RESET_ALL}", end='')
                        else:
                            print(f"\rDownloading: {downloaded/1024/1024:.1f}MB", end='')
                    
                    last_update = current_time
    
    elapsed = time.time() - start_time
    speed = downloaded / elapsed if elapsed > 0 else 0
    
    if use_colors:
        print(f"\n{Fore.GREEN}✓ Download completed in {Fore.CYAN}{elapsed:.1f}s{Fore.RESET} ({Fore.BLUE}{speed/1024/1024:.1f}MB/s{Style.RESET_ALL})")
    else:
        print(f"\nDownload completed in {elapsed:.1f}s ({speed/1024/1024:.1f}MB/s)")
    return True

def get_filename_from_headers(headers, format_info=None):
    """Extract filename from Content-Disposition header."""
    if 'content-disposition' in headers:
        match = re.search(r'filename="?([^"]+)"?', headers['content-disposition'])
        if match:
            filename = match.group(1)
            
            if format_info and 'extension' in format_info:
                base_name = os.path.splitext(filename)[0]
                filename = f"{base_name}{format_info['extension']}"
                logger.info(f"Set filename extension based on format: {filename}")
                
            return filename
    return None

def clean_filename(text):
    """Clean a string to make it suitable for a filename."""
    return re.sub(r'[\\/*?:"<>|]', '', text)

def download_book_by_query(query, config, interactive=False):
    """Main function to download a book by search query."""
    output_dir = config.get('output_dir', 'books/')
    
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
    search_url = construct_search_url(query, config)
    logger.info(f"Searching for query: {query}")
    logger.info(f"URL: {search_url}")
    
    # Use robust request for search
    search_start = time.time()
    print(f"Searching Anna's Archive for: {query}")
    
    response = robust_request(
        session, 
        search_url, 
        message=f"Searching for '{query}'",
        timeout=(10, 120)  # Longer timeout for search (connect, read)
    )
    
    if not response:
        logger.error("Search request failed after multiple attempts")
        print("❌ Search failed. Please check your internet connection and try again.")
        return False
    
    search_time = time.time() - search_start
    logger.info(f"Search completed in {search_time:.2f}s")
    
    books = extract_search_results(response.text, config)
    if not books:
        logger.error("No acceptable format books found for this query")
        print(f"❌ No books found for query: {query}")
        return False
    
    # Handle selection based on mode (interactive vs automatic)
    selected_book = None
    
    if interactive:
        # Always show selection menu in interactive mode
        selected_idx = display_selection_menu(books, config, config.get('use_colors', True))
        if selected_idx is None:
            logger.info("User cancelled selection")
            return False
        selected_book = books[selected_idx]
    else:
        # For automatic mode, use the first result by default
        selected_book = books[0]
        logger.info(f"Automatic mode: using first result: {books[0]['title']}")
    
    # Determine metadata about the selected book
    is_partial_match = selected_book.get('is_partial_match', False)
    match_type = "partial match" if is_partial_match else "direct match"
    format_display = selected_book['format_info']['display_name']
    
    logger.info(f"Selected {format_display} book ({match_type}): {selected_book['title']} by {selected_book.get('author', 'Unknown')}")
    
    # Navigate to book page to find download link
    book_url = urljoin(BASE_URL, selected_book['link'])
    logger.info(f"Accessing book page: {book_url}")
    
    response = robust_request(
        session, 
        book_url, 
        message=f"Loading book details",
        timeout=(10, 60)
    )
    
    if not response:
        logger.error("Book page request failed after multiple attempts")
        print("❌ Failed to access book details. Please try again.")
        return False
    
    download_link = extract_fast_download_link(response.text)
    if not download_link:
        logger.error("No download link found on the book page")
        print("❌ No download link found. This book may not be available for direct download.")
        return False
    
    # Start download process
    download_url = urljoin(BASE_URL, download_link)
    logger.info(f"Found download link: {download_url}")
    
    # Get file metadata before downloading
    head_response = robust_request(
        session, 
        download_url, 
        method="head", 
        message="Checking download details",
        timeout=(10, 30)
    )
    
    if not head_response:
        logger.error("Failed to get download metadata")
        print("❌ Failed to prepare download. Please try again.")
        return False
    
    # Determine filename, either from headers or construct from book info
    filename = get_filename_from_headers(head_response.headers, selected_book['format_info'])
    if not filename:
        title = clean_filename(selected_book['title'])
        author = clean_filename(selected_book.get('author', 'Unknown'))
        extension = selected_book['format_info']['extension']
        
        filename = f"{title} - {author}{extension}"
    
    output_path = os.path.join(output_dir, filename)
    logger.info(f"Downloading to: {output_path}")
    print(f"Preparing to download: {filename}")
    
    # Download the actual file
    download_success = download_file(session, download_url, output_path, selected_book['format_info'], config.get('use_colors', True))
    if download_success:
        logger.info(f"Successfully downloaded: {filename}")
        print(f"✅ Successfully downloaded: {filename}")
        return True
    else:
        logger.error("Download failed")
        print("❌ Download failed. Please try again.")
        return False

def interactive_mode(config, verbose):
    """Run the downloader in interactive mode, allowing for multiple queries to be processed."""
    output_dir = config.get('output_dir', 'books/')
    
    # Configure logging based on verbosity
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    # Display welcome message and instructions with colors
    print(f"\n{Style.BRIGHT}{Fore.CYAN}=== Anna's Archive Interactive Downloader ==={Style.RESET_ALL}")
    print(f"Output directory: {Fore.YELLOW}{output_dir}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Enter search queries one at a time. Type 'exit', 'quit', or press Ctrl+C to exit.")
    print(f"You can also paste multiple queries (one per line).")
    print(f"When multiple books are found, you'll get a selection menu.{Style.RESET_ALL}")
    print(f"{Style.BRIGHT}{Fore.CYAN}=========================================={Style.RESET_ALL}\n")
    
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
                search_url = construct_search_url(query, config)
                logger.info(f"URL: {search_url}")
                
                # Use robust request for search
                search_start = time.time()
                response = robust_request(
                    session, 
                    search_url, 
                    message=f"Searching for '{query}'",
                    timeout=(10, 120)  # Longer timeout for search
                )
                
                if not response:
                    logger.error("Search request failed after multiple attempts")
                    print(f"❌ Search failed for query: {query}")
                    continue
                
                search_time = time.time() - search_start
                logger.info(f"Search completed in {search_time:.2f}s")
                
                books = extract_search_results(response.text, config)
                
                if not books:
                    print(f"❌ No books found for query: {query}")
                    continue
                
                # Let user select which book to download
                selected_idx = display_selection_menu(books, config, config.get('use_colors', True))
                if selected_idx is None:
                    print(f"Download cancelled for query: {query}")
                    continue
                
                selected_book = books[selected_idx]
                print(f"Selected: {selected_book['title']} by {selected_book.get('author', 'Unknown')}")
                
                # Navigate to book page to find download link
                book_url = urljoin(BASE_URL, selected_book['link'])
                logger.info(f"Accessing book page: {book_url}")
                
                response = robust_request(
                    session, 
                    book_url, 
                    message=f"Loading book details",
                    timeout=(10, 60)
                )
                
                if not response:
                    logger.error("Book page request failed")
                    print(f"❌ Failed to access book page for query: {query}")
                    continue
                
                download_link = extract_fast_download_link(response.text)
                if not download_link:
                    print("❌ No download link found on the book page")
                    continue
                
                # Start download process
                download_url = urljoin(BASE_URL, download_link)
                logger.info(f"Found download link: {download_url}")
                
                # Get file metadata before downloading
                head_response = robust_request(
                    session, 
                    download_url, 
                    method="head", 
                    message="Checking download details",
                    timeout=(10, 30)
                )
                
                if not head_response:
                    logger.error("Failed to get download metadata")
                    print("❌ Failed to prepare download. Please try again.")
                    continue
                
                # Determine filename, either from headers or construct from book info
                filename = get_filename_from_headers(head_response.headers, selected_book['format_info'])
                if not filename:
                    title = clean_filename(selected_book['title'])
                    author = clean_filename(selected_book.get('author', 'Unknown'))
                    extension = selected_book['format_info']['extension']
                    
                    filename = f"{title} - {author}{extension}"
                
                output_path = os.path.join(output_dir, filename)
                print(f"Preparing to download: {filename}")
                
                # Download the actual file
                download_success = download_file(session, download_url, output_path, selected_book['format_info'], config.get('use_colors', True))
                if download_success:
                    print(f"✅ Successfully downloaded: {filename}")
                else:
                    print("❌ Download failed")
    
    except KeyboardInterrupt:
        print("\nExiting...")
    
    return 0

def debug_search(query, config, verbose=False):
    """Debug function to just search and print results without downloading."""
    output_dir = config.get('output_dir', 'books/')
    
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
    
    search_url = construct_search_url(query, config)
    logger.info(f"Searching for query: {query}")
    logger.info(f"URL: {search_url}")
    
    # Use robust request for search
    print(f"Searching Anna's Archive for: {query}")
    search_start = time.time()
    
    response = robust_request(
        session, 
        search_url, 
        message=f"Searching for '{query}'",
        timeout=(10, 120)  # Longer timeout for search
    )
    
    if not response:
        logger.error("Search request failed after multiple attempts")
        print("❌ Search failed. Please check your internet connection and try again.")
        return 1
    
    search_time = time.time() - search_start
    logger.info(f"Search completed in {search_time:.2f}s")
    
    debug_file = "results.html"
    with open(debug_file, "w", encoding="utf-8") as f:
        f.write(response.text)
    logger.info(f"Saved full HTML response to {debug_file}")
    
    md5_count = response.text.count('href="/md5/')
    logger.info(f"Direct count of 'href=\"/md5/' in HTML: {md5_count}")
    
    books = extract_search_results(response.text, config)
    
    print("\n===== DEBUG SEARCH RESULTS =====")
    print(f"Query: {query}")
    print(f"Search completed in: {search_time:.2f} seconds")
    print(f"Total results found: {len(books)}")
    print(f"Raw MD5 link count in HTML: {md5_count}")
    print(f"HTML saved to: {debug_file}")
    
    for i, book in enumerate(books):
        print(f"\nResult {i+1}:")
        print(f"  Title: {book['title']}")
        print(f"  Author: {book['author']}")
        print(f"  Format: {book['format']}")
        print(f"  Format Type: {book['format_info']['display_name']}")
        print(f"  Format Priority: {book['format_priority']}")
        print(f"  Link: {book['link']}")
        print(f"  Partial Match: {book['is_partial_match']}")
    
    return 0

def main():
    """Main entry point for the script."""
    # Load config file
    default_config_path = os.getenv('AA_CONFIG_PATH', 'config.json')
    
    # Set up command line argument parser
    parser = argparse.ArgumentParser(description='Download books from Anna\'s Archive by search query')
    
    # Add config file argument
    parser.add_argument('--config', type=str, default=default_config_path, help='Path to config file')
    
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
        subparser.add_argument('--output', '-o', help='Directory to save downloaded books (overrides config)')
        subparser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
        subparser.add_argument('--no-color', action='store_true', help='Disable colored output')
        
        # Add config override arguments using nargs='+' to accept multiple values
        subparser.add_argument('--formats', nargs='+', help='Formats to include (all others will be ignored)')
        subparser.add_argument('--content', nargs='+', help='Content types to include (all others will be ignored)')
        subparser.add_argument('--access', nargs='+', help='Access methods to include (all others will be ignored)')
        subparser.add_argument('--languages', nargs='+', help='Languages to include (all others will be ignored)')
    
    args = parser.parse_args()
    
    # Show help if no mode specified
    if not args.mode:
        parser.print_help()
        return 1
    
    # Configure logging based on verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Load config
    try:
        config = load_config(args.config)
        logger.info(f"Loaded configuration from {args.config}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1
    
    # Apply command-line overrides
    config = apply_command_line_overrides(config, args)
    
    # Create output directory if it doesn't exist
    output_dir = config.get('output_dir', 'books/')
    os.makedirs(output_dir, exist_ok=True)
    
    # Run the appropriate mode
    if args.mode == 'single':
        success = download_book_by_query(args.query, config, args.interactive)
        return 0 if success else 1
    elif args.mode == 'interactive':
        return interactive_mode(config, args.verbose)
    elif args.mode == 'debug':
        return debug_search(args.query, config, args.verbose)
    
    return 0

if __name__ == "__main__":
    main()