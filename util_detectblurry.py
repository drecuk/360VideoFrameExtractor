import cv2
import shutil
import os

def evaluate_blurry_image(image_path, grid_size=3, threshold=100.0, min_blurry_sectors=1):
    """
    Evaluates an image for partial blur by dividing it into a grid.
    Returns a tuple: (is_blurry, bad_chunks, total_chunks)
    """
    img = cv2.imread(image_path)

    # if image cannot be read, return empty result
    if img is None:
        return False, 0, 0

    # convert image to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape

    # calculate sector sizes
    sector_h = height // grid_size
    sector_w = width // grid_size

    blurry_sectors = 0
    total_sectors = grid_size * grid_size

    for row in range(grid_size):
        for col in range(grid_size):
            y_start = row * sector_h
            y_end = (row + 1) * sector_h
            x_start = col * sector_w
            x_end = (col + 1) * sector_w

            sector = gray[y_start:y_end, x_start:x_end]

            # use Variance of Laplacian to measure sharpness
            focus_measure = cv2.Laplacian(sector, cv2.CV_64F).var()

            if focus_measure < threshold:
                blurry_sectors += 1

    # Returns True only if the amount of blurry sectors meets/exceeds the user's minimum requirement
    is_partially_blurry = blurry_sectors >= min_blurry_sectors

    return is_partially_blurry, blurry_sectors, total_sectors


def move_confirmed_blurry(image_paths_list, dest_folder):
    """
    Moves a confirmed list of absolute image paths to the destination folder.
    """
    os.makedirs(dest_folder, exist_ok=True)
    moved_count = 0

    for img_path in image_paths_list:
        if os.path.exists(img_path):
            dest_path = os.path.join(dest_folder, os.path.basename(img_path))
            try:
                shutil.move(img_path, dest_path)
                moved_count += 1
            except Exception as e:
                print(f"Error moving {img_path}: {e}")

    return moved_count