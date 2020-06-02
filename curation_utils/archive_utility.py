import logging
import os
import pprint

import internetarchive

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s"
)


class ArchiveItem(object):
    """
    Represents an archive.org item.
    """
    def __init__(self, archive_id, metadata=None, config_file_path=None, mirrors_repo_structure=False):
        """
        
        :param archive_id: 
        :param config_file_path:
        :param mirrors_repo_structure: In archive item, place each file in a folder mirroring its local location.
        """
        self.mirrors_repo_structure = mirrors_repo_structure
        self.archive_id = archive_id
        self.archive_session = internetarchive.get_session(config_file=config_file_path)
        self.archive_item = internetarchive.get_item(archive_id, config_file=config_file_path)
        self.metadata = metadata
        logging.info(self.archive_item.identifier)

        self.original_item_files = list(filter(
            lambda x: x["source"] == "original" and not x["name"].startswith(self.archive_item.identifier) and not x[
                "name"].startswith ("_"), self.archive_item.files))
        self.original_item_file_names = sorted(map(lambda x: x["name"], self.original_item_files))

    def __str__(self, *args, **kwargs):
        return self.archive_id

    def update_metadata(self, metadata):
        self.metadata = metadata
        if not self.archive_item.exists:
            logging.error("Archive item ought to exist for this to work, but it does not.")
        else:
            self.archive_item.modify_metadata(metadata=self.metadata)

    def get_remote_name(self, file_path):
        """
        
        :param file_path: A path like git_repo_name/mp3/xyz.mp3
        :return: If self.mirrors_repo_structure : git_repo_name/xyz.mp3, else: xyz.mp3
        """
        basename = os.path.basename(file_path)
        return os.path.join(os.path.basename(os.path.dirname(os.path.dirname(file_path))), basename) if self.mirrors_repo_structure else basename

    def delete_unaccounted_for_files(self, all_files, dry_run=False):
        """
        Delete all unaccounted-for-files among all_files.
    
        May not satisfactorily delete files under directories.
        :param all_files: This has to include exactly _every_ file that is expected to be present in the archive item.
        """
        local_basenames = list(map(os.path.basename, all_files))
        # Deletion
        false_original_item_file_names = list(
            filter(lambda x: x not in local_basenames, self.original_item_file_names))
        if len(false_original_item_file_names) > 0:
            logging.info("************************* Deleting %s the below unaccounted for files: \n%s", self, pprint.pformat(
                false_original_item_file_names))
        if len(false_original_item_file_names) > 0 and not dry_run:
            internetarchive.delete(self.archive_item.identifier, files=false_original_item_file_names, cascade_delete=True, access_key=self.archive_session.access_key, secret_key=self.archive_session.secret_key)

    def update_archive_item(self, file_paths, overwrite_all=False, dry_run=False):
        """
        Upload some files.
    
        :param file_paths: List of Strings.
        :param overwrite_all: Boolean.
        :param dry_run: Boolean.
        """
        if len(file_paths) == 0:
            logging.debug("file_paths is empty.")
            import traceback
            # for line in traceback.format_stack():
            #     logging.debug(line.strip())
            return 
        logging.info("************************* Now uploading to %s from %s", self, os.path.dirname(file_paths[0]))
        remote_names = list(map(lambda file_path: self.get_remote_name(file_path), file_paths))
        remote_name_to_file_path = dict(
            zip(remote_names, file_paths))
        remote_name_to_file_path_filtered = remote_name_to_file_path
        if not overwrite_all:
            remote_name_to_file_path_filtered = dict(
                filter(lambda item: item[0] not in self.original_item_file_names, remote_name_to_file_path.items()))
        logging.info(pprint.pformat(remote_name_to_file_path_filtered.items()))
        if dry_run:
            logging.warning("Not doing anything - in dry_run mode")
        else:
            if len(remote_name_to_file_path_filtered) > 0:
                # checksum=True seems to not avoid frequent reuploads. Archive item mp3 checksum end up varying because of metadata changes? 
                responses = self.archive_item.upload(remote_name_to_file_path_filtered, verbose=False, checksum=False, verify=False, metadata=self.metadata)
                logging.info(pprint.pformat(dict(zip(remote_name_to_file_path_filtered.keys(), responses))))
                # It is futile to do the below as archive.org says that the file does not exist for newly uploaded files.
                # for basename in remote_name_to_file_path_filtered.keys():
                #     self.update_mp3_metadata(mp3_file=basename_to_file[basename])
            else:
                logging.warning("Found nothing to update!")

    def download_original_files(self, destination_dir, file_prefix="", skip_existing=True):
        import wget
        os.makedirs(destination_dir, exist_ok=True)
        for url in self.original_item_files:
            extension = os.path.splitext(url)[1]
            remote_file_name = os.path.basename(url)
            out_file = os.path.join(destination_dir, "%s%s" % (file_prefix, remote_file_name))
            if not skip_existing or not os.path.exists(out_file):
                logging.info("Getting %s as %s", url, out_file)
                wget.download(url=url, out=out_file)
            else:
                logging.info("Skipping existing file %s", out_file)
