#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <numpy/arrayobject.h>
static_assert(sizeof(void*) == 8, "Expected ARM64 pointers");
static PyModuleDef module = {PyModuleDef_HEAD_INIT, "arm_python_smoke", nullptr, -1, nullptr};
PyMODINIT_FUNC PyInit_arm_python_smoke() { return PyModule_Create(&module); }
