# Anna's Archive Downloader

A Python script for automatically downloading books from Anna's Archive using ISBNs.

## Features

- Search Anna's Archive for books by keyword (I usually use ISBN but sometimes title)
- Select the best match based on search results
- Automatically download books via fast partner servers
- Multiple authentication options including direct account ID
- Detailed logging and progress reporting

## Requirements

- Python 3.8+
- Requests
- BeautifulSoup4

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

## Usage

### Basic Usage

```bash
python annas_downloader.py 9781250881205 --account-id "your_account_id_cookie_value" --output books/
```

### Command Line Options

```
usage: annas_downloader.py [-h] [--auth AUTH | --curl CURL | --account-id ACCOUNT_ID] [--output OUTPUT] [--verbose]
                           isbn

Download books from Anna's Archive by ISBN

positional arguments:
  isbn                  ISBN of the book to download

options:
  -h, --help            show this help message and exit
  --auth AUTH           Path to JSON file with authentication headers
  --curl CURL           Path to file containing curl command with authentication
  --account-id ACCOUNT_ID
                        Anna's Archive account ID cookie value
  --output OUTPUT, -o OUTPUT
                        Directory to save downloaded books
  --verbose, -v         Enable verbose logging
```

### Authentication Options

#### Using an Account ID (Recommended)

Get your account ID cookie value from Anna's Archive by logging in and inspecting your cookies.

```bash
python annas_downloader.py 9781250881205 --account-id "eyJhIjoiOUtXZE5OTiIsImlhdCI6MTc0MTQ5NzAyMX0.example" --output books/
```

#### Using a curl Command

```bash
# Save your curl command to a file
echo 'curl "https://annas-archive.org/search?..." -H "accept: text/html..." -b "aa_account_id2=..."' > auth.txt

# Use the curl file for authentication
python annas_downloader.py 9781250881205 --curl auth.txt --output books/
```

#### Using a JSON Headers File

```bash
# Create a JSON file with your headers
echo '{"Cookie": "aa_account_id2=your_cookie_value"}' > headers.json

# Use the headers file for authentication
python annas_downloader.py 9781250881205 --auth headers.json --output books/
```

## How It Works

1. **Search Phase**: Searches Anna's Archive with specific parameters to find the most relevant book match
2. **Selection Phase**: Selects the best book from search results
3. **Download Phase**: Finds the fastest download link and saves the book file

## Notes

- The script will only search for and download books available through Anna's Archive directly (not external sources)
- By default, it will download EPUB format books in English
- Search parameters are customizable by modifying the `DEFAULT_SEARCH_PARAMS` dictionary in the script

## Customizing Search Parameters

The script uses a predefined set of search parameters that you can modify in the code:

```python
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