import os
import glob
import locale
import sys

def convert_csv_to_utf8(directory):
    """
    Attempts to convert non-UTF-8 CSV files in a directory to UTF-8.
    """
    # Set default encoding to UTF-8 for print statements
    sys.stdout.reconfigure(encoding='utf-8')

    # Get the system's preferred encoding as a fallback
    fallback_encoding = locale.getpreferredencoding()
    print(f"Using fallback encoding: {fallback_encoding}")

    for filepath in glob.glob(os.path.join(directory, "*.csv")):
        print(f"Processing {os.path.basename(filepath)}...")
        try:
            # First, try to read the file with UTF-8 to check if it's already compliant
            with open(filepath, 'r', encoding='utf-8') as f:
                f.read()
            print("  File is already UTF-8. Skipping.")
            continue
        except UnicodeDecodeError:
            # If it fails, the file is not UTF-8
            print(f"  File is not UTF-8. Attempting conversion using '{fallback_encoding}'.")
            try:
                # Read with the fallback encoding
                with open(filepath, 'r', encoding=fallback_encoding, errors='replace') as f_in:
                    content = f_in.read()
                
                # Write back with UTF-8 encoding
                with open(filepath, 'w', encoding='utf-8') as f_out:
                    f_out.write(content)
                print(f"  Successfully converted '{os.path.basename(filepath)}' to UTF-8.")
            except Exception as e:
                print(f"  Failed to convert '{os.path.basename(filepath)}' with fallback encoding: {e}")
        except Exception as e:
            print(f"  An unexpected error occurred while processing '{os.path.basename(filepath)}': {e}")

if __name__ == "__main__":
    target_directory = "export_data"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(script_dir, target_directory)
    
    if not os.path.isdir(full_path):
        print(f"Error: Directory not found at '{full_path}'")
    else:
        print("Starting file encoding conversion...")
        convert_csv_to_utf8(full_path)
        print("\nConversion process finished.")