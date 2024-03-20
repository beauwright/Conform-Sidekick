import os
import argparse
from typing import Tuple
import uuid
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

def make_even_dimensions(image_path: str, output_path: str) -> str | None:
    try:
        img: Image = Image.open(image_path)
        size: Tuple[int, int] = img.size
        width, height = size

        # Check if width or height are odd and adjust them if necessary
        new_width: int = width if width % 2 == 0 else width + 1
        new_height: int = height if height % 2 == 0 else height + 1

        # If the dimensions did not change, no need to save the image
        if new_width != width or new_height != height:
            # Resize the image
            img_resized: Image = img.resize((new_width, new_height), Image.LANCZOS)

            # Save the resized image
            img_resized.save(output_path)

            print(f"Image saved to {output_path}")
            return output_path
        else:
            print(f"Image {image_path} was sent for conversion but does not contain an odd resolution.")
            return None
    except UnidentifiedImageError:
        print(f"ERROR: Unable to read the file {image_path}. Skipping this file.")
        return None
    except FileNotFoundError:
        print(f"ERROR: Unable to find the file in the mediapool located at {image_path}.")
        return None

def convert_all_photos_in_folder(directory) -> None:
    # Make a new directory for converted photos
    output_directory = os.path.join(directory, 'converted_photos', uuid.uuid4())
    os.makedirs(output_directory, exist_ok=False)

    # List all files in the directory
    for root, dirs, files in os.walk(directory):
        for file_name in files:
            # Check if the file is an image (PNG, JPG, TIFF, or HEIC)
            if file_name.lower().endswith(('png', 'jpg', 'jpeg', 'tiff')):
                file_path = os.path.join(root, file_name)
                output_path = os.path.join(output_directory, file_name)
                
                # Convert image to have even dimensions
                make_even_dimensions(file_path, output_path)

def convert_single_photo(file_path: str) -> str | None:
    # Check if the file is an image (PNG, JPG, TIFF, or HEIC)
    directory = os.path.dirname(file_path)
    file_name, file_extension = os.path.splitext(os.path.basename(file_path))

    if file_extension.lower().endswith(('png', 'jpg', 'jpeg', 'tiff', 'heic')):
        output_path = os.path.join(directory, f"{file_name}_converted_{uuid.uuid4()}{file_extension}")

        # Convert image to have even dimensions
        converted_file_path = make_even_dimensions(file_path, output_path)
        return converted_file_path
    else:
        print(f"Unsupported file type: {file_name}{file_extension}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Convert images to have even dimensions')
    parser.add_argument('directory', type=str, help='Directory containing images')
    args = parser.parse_args()
    
    convert_all_photos_in_folder(args.directory)

if __name__ == '__main__':
    main()
