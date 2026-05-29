#!/usr/bin/env python3
import os

SHARED_DIR = os.path.join(os.path.sep, 'shared')

GOOGLE_URL = "http://metadata.google.internal/computeMetadata/v1/instance/attributes"

PACKAGES = [
    # required to run
    'curl',
    'screen',
    'openjdk-17-jdk',
    'git',
    'python3-pip',
    # just useful
    'zip',
    'less',
    'emacs', 'vim',
    'python3-dev',
    'python3-setuptools',
    'wget'
]


# Using a decorator to reduce logging annoyances
# Referenced this guide for construction:
# https://www.thecodeship.com/patterns/guide-to-python-function-decorators/
def bookends(func):
    """
    Print the `func`'s name and args at start and completion of function.
    e.g. `def install_packages()` with `@bookends` decorator will output the following

    install_packages...
    <stdout+stderr of the os.system calls>
    install_packages...DONE
    """
    def wrapper(*args, **kwargs):
        print(f"{func.__name__}...")
        result = func(*args, **kwargs)
        print(f"{func.__name__}...DONE")
        return result
    return wrapper


@bookends
def create_directories():
    os.system(f'mkdir -p {SHARED_DIR}/civic-pubtator')
    os.system(f'chmod -R 777 {SHARED_DIR}')


@bookends
def install_packages():
    os.system('apt-get update')
    os.system('apt-get install -y ' + ' '.join(PACKAGES))
    # Python deps
    os.system('python3 -m pip install "requests>=2.20.0"')


@bookends
def clone_civic_pubtator():
    old_dir = os.getcwd()
    os.chdir(SHARED_DIR)
    print(f"git clone https://github.com/griffithlab/civic-pubtator.git")

    status_code = os.system(f"git clone https://github.com/griffithlab/civic-pubtator.git")
    os.chdir(old_dir)


def add_aliases():
    print(f"echo ll=\'ls -l\' >> ~/.bash_aliases")
    os.system("echo ll=\'ls -l\' >> ~/.bash_aliases")


def _fetch_instance_info(name):
    import requests
    url = "/".join([GOOGLE_URL, name])
    response = requests.get(url, headers={'Metadata-Flavor': 'Google'})
    if not response.ok:
        raise Exception("GET failed for {}".format(url))
    return response.text


@bookends
def startup_script():
    create_directories()
    install_packages()
    clone_civic_pubtator()
    add_aliases()


if __name__ == '__main__':
    startup_script()
