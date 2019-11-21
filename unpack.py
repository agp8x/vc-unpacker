import argparse
import tempfile
import zipfile

from collections import namedtuple
from os import makedirs, listdir, walk
from os.path import basename, join as path_join, split as path_split
from pathlib import Path
from shutil import move
from subprocess import run, DEVNULL

import toml

unpackers = {
	".zip": "unzip^-o^{file}^-d^{target}",
	".rar": "unrar^x^-o+^{file}^{target}",
	".tar.gz": "tar^-xzf^{file}^-C^{target}",
	".7z": "7z^x^{file}^-o{target}",
	".pdf": "mv^{file}^{target}",
}


class Submission:
	def __init__(self, full_name, surname, first_names, files, config):
		self.full_name = full_name
		self.surname = surname
		self.first_names = first_names
		self.files = files
		self.notes = []
		self.total_points = config.points
		self.allowed_suffixes = config.allowed_suffixes
		self.file_limit = config.file_limit
		self.template = config.template
		self.filetypes = config.content_filetypes
		self.warnings = config.warnings
	
	def validate(self):
		if len(self.files) > self.file_limit:
			self.notes.append(f"more than {self.file_limit} file")
		for file in self.files:
			if not Path(file).suffix in self.allowed_suffixes:
				self.notes.append(f"wrong filetype ({file})")
			if "^" in file:
				self.notes.append(f"illegal char in filename ({file})")
		return -len(self.notes)
	
	def validate_file(self, path, base):
		file = Path(path)
		suffix = file.suffix
		if not suffix in self.filetypes:
			cleared = path.replace(base, "")
			filetype = suffix[1:]
			if not filetype in self.warnings:
				self.notes.append(f"illegal filetype '{suffix}' ({cleared})")
			else:
				self.notes.append(self.warnings[filetype].format(path=cleared, suffix=suffix, name=file.name))
	
	def validate_files(self, target, base):
		for root, dirs, files in walk(target):
			if files:
				for file in files:
					self.validate_file(path_join(root, file), base)
	
	def unpack(self, base="."):
		target = path_join(base, f"{self.surname}-{self.first_names}")
		makedirs(target, exist_ok=True)
		for f in self.files:
			filetype = "".join(Path(f).suffixes)
			if filetype in unpackers:
				cmd = unpackers[filetype].format(file=f,target=target).split("^")
				r = run(cmd, stdout=DEVNULL)
				if r.returncode:
					self.notes.append(f"unpack fail: {r.stderr} @ {f} ({cmd}")
				self.validate_files(target, base)
			else:
				if filetype[1:] in self.warnings:
					self.notes.append(self.warnings[filetype[1:]].format(path=f, suffix=filetype, name=f))
				else:
					self.notes.append(f"wrong filetype/name ({f})")
				move(f, target)
	
	def ratings(self):
		notes = ""
		if self.notes:
			notes = "* "
			notes += "\n* ".join(self.notes)
		return self.template.format(
			full_name=self.full_name,
			max=self.total_points,
			notes=notes
		)
	
	def __repr__(self):
		return f"Submission(full_name={self.full_name}, surname={self.surname}, first_names={self.first_names}, files={self.files})"

def submission_info(path, config):
	full_name = basename(path).split("_")[0]
	surname = full_name.split()[-1]
	first_names = full_name[:-len(surname)-1]
	files = []
	for root, dirs, files in walk(path):
		files.extend([path_join(path,file) for file in files])
	files = list(filter(lambda x:x.startswith("/"), files))
	return Submission(full_name, surname, first_names, files, config)

def load_config(path):
	Config = namedtuple("Config", ["points", "allowed_suffixes", "file_limit", "template", "content_filetypes", "warnings"])
	config = toml.load(path)
	return Config(
		config["assignment"]["points"],
		config["assignment"]["allowed_suffixes"],
		config["assignment"]["file_limit"],
		config["assignment"]["template"],
		config["assignment"]["content_filetypes"],
		config["assignment"]["warnings"]
	)

def unpack(args):
	ratings = []
	makedirs(args.target, exist_ok=True)
	config = load_config(args.config)
	with zipfile.ZipFile(args.file, "r") as zip, tempfile.TemporaryDirectory() as tmp:
		zip.extractall(tmp)
		for i in listdir(tmp):
			s = submission_info(path_join(tmp,i), config)
			s.validate()
			s.unpack(args.target)
			ratings.append(s.ratings())
	ratepath = path_join(args.target, "ratings.rst")
	with open(ratepath, "w") as out:
		out.write("\n".join(ratings))
			

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("config")
	parser.add_argument("file")
	parser.add_argument("target", default="x", nargs="?")
	
	args = parser.parse_args()
	
	unpack(args)
