import os
import shutil


def concatenate_files(input_path_list, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path,'wb') as outfile:
        for f in input_path_list:
            with open(f,'rb') as fd:
                shutil.copyfileobj(fd, outfile)
            outfile.write("\n".encode())