import os
import shutil


def concatenate_files(input_path_list, output_path, add_newline_inbetween=False):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path,'wb') as outfile:
        for f in input_path_list:
            with open(f,'rb') as fd:
                shutil.copyfileobj(fd, outfile)
            if add_newline_inbetween:
                outfile.write("\n".encode())

