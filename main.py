import yaml
from pixivapi import pixiv

def main():
	with open('config.yaml', 'r') as f:
		config = yaml.load(f)

	p = pixiv.Pixiv()
	p.configure(config)

	illust = p.get_illust(58550366)

	p.download(illust)

if __name__ == '__main__':
	main()
