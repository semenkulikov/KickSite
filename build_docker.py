import os
import subprocess


def main():
    dockerbuildname = "Webstreams".lower()
    version = "latest"  # Set your version here
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
    tarball_path = os.path.join(dist_dir, f"{dockerbuildname}_{version}.tar")
    save_cmd = ['docker', 'save', '-o', tarball_path, image_name_with_version]
    subprocess.run(save_cmd)

   # print(f"Image saved as tarball at {tarball_path}")


if __name__ == "__main__":
    main()
