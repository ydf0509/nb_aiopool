
import os
import sys
import git_nb_aiopool

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.system("python -m build")
os.system("twine upload dist/*")
os.system("rm -rf dist")