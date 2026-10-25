"""SOTN Co-op (design/M9): python-for-android's `android` recipe, built without build isolation
(an isolated build found no Cython), like android/recipes/pyjnius."""

from pythonforandroid.recipes.android import AndroidRecipe


class IsolationFreeAndroidRecipe(AndroidRecipe):
    extra_build_args = ["--no-isolation"]


recipe = IsolationFreeAndroidRecipe()
