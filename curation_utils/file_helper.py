import os


def concatenate_files(input_path_list, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as outfile:
        for fname in input_path_list:
            with open(fname) as infile:
                for line in infile:
                    outfile.write(line)