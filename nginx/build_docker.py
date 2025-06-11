import os
import subprocess
import zipfile


def zip_file_with_best_compression_v3(source_file, zip_file_name):
    """
    Compresses a file using the best compression available for ZIP format.
    Supports both absolute and relative file paths. The ZIP file is created
    in the same directory as the source file.

    :param source_file: The path of the file to be compressed. Can be relative or absolute.
    :param zip_file_name: The name of the resulting ZIP file (without path).
    """

    # Determine the directory of the source file
    source_dir = os.path.dirname(source_file)

    # Construct the full path for the zip file
    full_zip_path = os.path.join(source_dir, zip_file_name)

    # Zip the file with best compression
    with zipfile.ZipFile(full_zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        # Add the file to the zip, use only the basename in the zip
        zipf.write(source_file, arcname=os.path.basename(source_file))

def main():
    dockerbuildname = "nginx".lower()
    version = "starkinc"  # Set your version here
    image_name_with_version = f"{dockerbuildname}:{version}"

    # Build the Docker image
    docker_cmd = ['docker', 'build', '-t', image_name_with_version, '.']
    completed_process = subprocess.run(docker_cmd)

    # Ensure 'dist' directory exists or create it
    dist_dir = "dist"
    if not os.path.exists(dist_dir):
        os.makedirs(dist_dir)
    print("saving image")
    # Save the Docker image as a tarball in the 'dist' directory
    tarball_path = os.path.join(dist_dir, f"{dockerbuildname}.tar")
    save_cmd = ['docker', 'save', '-o', tarball_path, image_name_with_version]
    subprocess.run(save_cmd)

    print(f"Image saved as tarball at {tarball_path}")
    print("creating zip...")
    zip_file_with_best_compression_v3(tarball_path,"dist.zip")

if __name__ == "__main__":
    main()
