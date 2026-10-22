"""SOTN Co-op (design/M9): python-for-android's pyjnius recipe, built without build isolation, so
it uses the Cython p4a installs into its host Python (an isolated build found none)."""

from pythonforandroid.recipes.pyjnius import PyjniusRecipe


class IsolationFreePyjniusRecipe(PyjniusRecipe):
    extra_build_args = ["--no-isolation"]


recipe = IsolationFreePyjniusRecipe()
