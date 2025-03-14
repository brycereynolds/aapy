# Anna's Archive Downloader

A Python script for automatically downloading books from Anna's Archive using search queries (titles, authors, ISBNs, etc).

## Features

- Search Anna's Archive using any search query (title, author, ISBN, etc.)
- Interactive selection from all available format options
- Automatically download books via fast partner servers
- Simple environment variable authentication
- Detailed logging and progress reporting
- Customizable configuration via JSON file

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

6. **Set up authentication and configuration**:

   ```bash
   # Copy the example .env file
   cp .env.example .env
   
   # Edit the .env file with your Anna's Archive account ID
   # You can find this by logging into Anna's Archive and checking your cookies
   # Look for the "aa_account_id2" cookie value
   
   # Make sure config.json exists (should be provided with the script)
   # If not, create it using the template from the documentation
   ```

## Configuration

The script uses a `config.json` file for all search parameters, format preferences, and output settings. The default configuration is included, but you can customize it for your needs:

```json
{
  "search": {
    "index": "",
    "page": "1",
    "display": "",
    "sort": ""
  },
  "content": {
    "types": [
      "book_fiction",
      "book_nonfiction",
      "book_unknown",
      "magazine",
      "book_comic",
      "standards_document",
      "other",
      "musical_score"
    ],
    "ignore": [
      "book_nonfiction",
      "book_unknown",
      "magazine",
      "book_comic",
      "standards_document",
      "other",
      "musical_score"
    ]
  },
  "formats": {
    "ignore": [
      "pdf",
      "mobi",
      "fb2",
      "cbr"
    ],
    "definitions": {
      "epub": {
        "priority": 100,
        "extension": ".epub",
        "icon": "📙",
        "display_name": "EPUB",
        "content_type": "application/epub+zip"
      },
      "pdf": {
        "priority": 80,
        "extension": ".pdf",
        "icon": "📑",
        "display_name": "PDF",
        "content_type": "application/pdf"
      },
      "mobi": {
        "priority": 60,
        "extension": ".mobi",
        "icon": "📕",
        "display_name": "MOBI",
        "content_type": "application/x-mobipocket-ebook"
      },
      "fb2": {
        "priority": 40,
        "extension": ".fb2",
        "icon": "📄",
        "display_name": "FB2",
        "content_type": "application/fb2"
      },
      "cbr": {
        "priority": 20,
        "extension": ".cbr",
        "icon": "🗃️",
        "display_name": "CBR",
        "content_type": "application/x-cbr"
      }
    }
  },
  "access": {
    "types": [
      "aa_download",
      "external_download",
      "external_borrow",
      "external_borrow_printdisabled",
      "torrents_available"
    ],
    "ignore": [
      "external_download",
      "external_borrow",
      "external_borrow_printdisabled",
      "torrents_available"
    ]
  },
  "languages": {
    "types": [
      "en",
      "zh",
      "ru",
      "es",
      "fr",
      "de",
      "it",
      "pt",
      "pl",
      "nl"
    ],
    "ignore": [
      "zh",
      "ru",
      "es",
      "fr",
      "de",
      "it",
      "pt",
      "pl",
      "nl"
    ]
  },
  "output_dir": "books/"
}
```

### Configuration Options:

- **search**: Basic search parameters
- **content**: Content types configuration
  - **types**: All available content types
  - **ignore**: Content types to exclude from search
- **formats**: File formats configuration
  - **ignore**: Formats to exclude from search
  - **definitions**: Detailed metadata for each format
    - **priority**: Numeric priority value (higher = preferred)
    - **extension**: File extension (e.g., ".epub")
    - **icon**: Emoji icon for display
    - **display_name**: Human-readable format name
    - **content_type**: MIME type for the format
- **access**: Access methods configuration
  - **types**: All available access methods
  - **ignore**: Access methods to exclude
- **languages**: Languages configuration
  - **types**: All available languages
  - **ignore**: Languages to exclude
- **output_dir**: Default directory to save downloaded books

## Usage

### Operation Modes

The script supports three primary modes of operation:

#### 1. Single Mode

Search for a book with a specific query and download it:

```bash
python aapy.py single "Project Hail Mary" --output books/
```

You can also search by ISBN:

```bash
python aapy.py single "9781250881205"
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

### Command Line Options

```
usage: aapy.py {single,interactive,debug} [-h] [--config CONFIG] [--output OUTPUT] [--verbose] 
                                          [--formats FORMAT [FORMAT ...]]
                                          [--content CONTENT [CONTENT ...]]
                                          [--access ACCESS [ACCESS ...]]
                                          [--languages LANGUAGE [LANGUAGE ...]]

Download books from Anna's Archive by search query

modes:
  single               Download a book by search query (title, author, ISBN, etc)
  interactive          Run in interactive mode to download multiple books
  debug                Debug search results without downloading

options:
  -h, --help            show this help message and exit
  --config CONFIG       Path to config file (default: config.json)
  --output OUTPUT, -o OUTPUT
                        Directory to save downloaded books (overrides config's output_dir)
  --verbose, -v         Enable verbose logging
  --formats FORMAT [FORMAT ...]
                        Formats to include (all others will be ignored)
  --content CONTENT [CONTENT ...]
                        Content types to include (all others will be ignored)
  --access ACCESS [ACCESS ...]
                        Access methods to include (all others will be ignored)
  --languages LANGUAGE [LANGUAGE ...]
                        Languages to include (all others will be ignored)
```

### Command Line Configuration Overrides

You can override configuration settings through command-line arguments. When you specify options on the command line, all other options of that type will be automatically ignored:

```bash
# Only include EPUB and PDF formats (ignoring all others)
python aapy.py single "Dune Herbert" --formats epub pdf

# Only include fiction books
python aapy.py single "Asimov" --content book_fiction

# Only include direct downloads from Anna's Archive
python aapy.py single "Sapiens" --access aa_download

# Only include English and Spanish books
python aapy.py single "Don Quixote" --languages en es

# Use a custom config file
python aapy.py interactive --config my_custom_config.json
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

1. **Search Phase**: Searches Anna's Archive with parameters from config.json to find books matching your query
2. **Selection Phase**: Presents an interactive menu of all matching books with format details
3. **Download Phase**: Finds the fastest download link and saves the book file

## Advanced Configuration

### Customizing Search Parameters

You can customize the search parameters in the config.json file to:

1. **Adjust format priorities**:
   ```json
   "formats": {
     "definitions": {
       "pdf": {
         "priority": 120
       },
       "epub": {
         "priority": 100
       }
     }
   }
   ```

2. **Include different content types**:
   ```json
   "content": {
     "ignore": ["magazine", "book_comic"]
   }
   ```

3. **Change language preferences**:
   ```json
   "languages": {
     "ignore": ["zh", "ru"]
   }
   ```

### Adding New Format Types

You can add support for new format types by adding them to the config:

1. Add a complete definition under `definitions`:

```json
"formats": {
  "ignore": ["mobi", "fb2", "cbr"],
  "definitions": {
    "djvu": {
      "priority": 90,
      "extension": ".djvu",
      "icon": "📔",
      "display_name": "DJVU",
      "content_type": "image/vnd.djvu"
    }
  }
}
```

This extensible approach lets you add support for new formats without changing any code.

## Quick Start

For convenience, a `start.sh` script is included to quickly start the interactive mode:

```bash
# Make the script executable
chmod +x start.sh

# Run the script
./start.sh
```

## Disclaimer

This tool is provided for educational and research purposes only. Please respect copyright laws and the terms of service of Anna's Archive.