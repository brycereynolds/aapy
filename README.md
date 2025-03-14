# Anna's Archive Downloader

A Python script for automatically downloading books from Anna's Archive using search queries (ISBNs, titles, authors, etc).

## Features

- Search Anna's Archive using any search query (ISBN, title, author, etc.)
- Interactive selection from all available format options
- Automatically download books via fast partner servers
- Simple environment variable authentication
- Detailed logging and progress reporting

## Requirements

- Python 3.8+
- Requests
- BeautifulSoup4
- InquirerPy
- python-dotenv

## Installation

### Setting up with pyenv (recommended)

1. **Install pyenv** if you don't have it already:

   ```bash
   # macOS
   brew install pyenv
   
   # Ubuntu/Debian
   curl https://pyenv.run | bash
   ```

2. **Configure your shell** by adding the following to your profile file (`.bashrc`, `.zshrc`, etc.):

   ```bash
   export PATH="$HOME/.pyenv/bin:$PATH"
   eval "$(pyenv init --path)"
   eval "$(pyenv init -)"
   ```

3. **Install Python** with pyenv:

   ```bash
   pyenv install 3.11.0  # or any other version 3.8+
   ```

4. **Create a virtual environment**:

   ```bash
   # Navigate to the project directory
   cd path/to/annas-downloader
   
   # Create a virtual environment
   pyenv local 3.11.0
   python -m venv .venv
   
   # Activate the virtual environment
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

5. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

6. **Set up authentication**:

   ```bash
   # Copy the example .env file
   cp .env.example .env
   
   # Edit the .env file with your Anna's Archive account ID
   # You can find this by logging into Anna's Archive and checking your cookies
   # Look for the "aa_account_id2" cookie value
   ```

## Usage

### Operation Modes

The script supports three primary modes of operation:

#### 1. Single Mode

Search for a book with a specific query and download it:

```bash
python aapy.py single "9781250881205" --output books/
```

You can also search by title:

```bash
python aapy.py single "Project Hail Mary"
```

#### 2. Interactive Mode

Start an interactive session for multiple searches and downloads:

```bash
python aapy.py interactive
```

This mode allows you to:
- Enter multiple search queries (one at a time)
- Select from all available formats for each book
- Cancel any download at any point

#### 3. Debug Mode

Search for books without downloading them (useful for testing and troubleshooting):

```bash
python aapy.py debug "Foundation Asimov"
```

### Selection Menu

All modes present an interactive selection menu that shows:
- Book title and author
- Format information (EPUB 📙, PDF 📑, MOBI 📕)
- File size when available
- Option to cancel the download

This allows you to make an informed choice even when only one result is found.

### Command Line Options

```
usage: aapy.py {single,interactive,debug} [-h] [--output OUTPUT] [--verbose]

Download books from Anna's Archive by search query

modes:
  single               Download a book by search query (ISBN, title, etc)
  interactive          Run in interactive mode to download multiple books
  debug                Debug search results without downloading

options:
  -h, --help            show this help message and exit
  --output OUTPUT, -o OUTPUT
                        Directory to save downloaded books (overrides OUTPUT_DIR in .env)
  --verbose, -v         Enable verbose logging
```

### Authentication

Authentication is handled via the `.env` file, which should contain your Anna's Archive account ID:

```
AA_ACCOUNT_ID=your_account_id_here
OUTPUT_DIR=books/
```

To find your account ID:
1. Log in to Anna's Archive in your browser
2. Open your browser's developer tools (F12 or right-click → Inspect)
3. Go to the Storage or Application tab (depends on browser)
4. Look for Cookies → annas-archive.org
5. Find the cookie named `aa_account_id2` and copy its value
6. Paste this value in your `.env` file

## How It Works

1. **Search Phase**: Searches Anna's Archive with specific parameters to find books matching your query
2. **Selection Phase**: Presents an interactive menu of all matching books with format details
3. **Download Phase**: Finds the fastest download link and saves the book file

## Notes

- The script will only search for and download books available through Anna's Archive directly (not external sources)
- By default, it prioritizes EPUB format, then PDF, then MOBI
- Search parameters are customizable by modifying the `DEFAULT_SEARCH_PARAMS` dictionary in the script

## Customizing Search Parameters

The script uses a predefined set of search parameters that you can modify in the code:

```python
DEFAULT_SEARCH_PARAMS = {
    # Basic search parameters
    'index': '',
    'page': '1',
    'q': '',  # Will be set to your search query
    'display': '',
    'sort': '',
    
    # Content type parameters
    'content': [
        'anti__book_nonfiction',  # Exclude non-fiction
        'book_fiction',           # Include fiction
        # ...other content parameters...
    ],
    
    # File format parameters
    'ext': [
        'anti__pdf',   # Exclude PDF
        'epub',        # Include EPUB
        # ...other format parameters...
    ],
    
    # ...and so on...
}
```

## Disclaimer

This tool is provided for educational and research purposes only. Please respect copyright laws and the terms of service of Anna's Archive.