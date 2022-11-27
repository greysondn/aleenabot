import setuptools

with open("readme.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name='aleenabot',
    version='0.0.1',
    author='J. "Dorian Greyson" L.',
    author_email='greysondn@gmail.com',
    description='main manage-my-everything bot',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='',
    project_urls = {
        "Bug Tracker": ""
    },
    packages=['aleenabot'],
    install_requires=[
    ],
)