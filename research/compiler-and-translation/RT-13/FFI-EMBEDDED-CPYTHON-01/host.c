#include <Python.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct {
    PyThreadState *owner;
    PyObject *callback;
    unsigned generation;
} Callback;

static void require(int condition) {
    if (!condition)
        abort();
}

static void start_runtime(const char *root) {
    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    PyStatus status = PyConfig_SetBytesString(&config, &config.home, root);
    if (!PyStatus_Exception(status))
        status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status))
        Py_ExitStatusException(status);
}

static void create(Callback *slot, PyThreadState *main_state) {
    static const char source[] =
        "counter = 0\n"
        "def step(value):\n"
        "    global counter\n"
        "    if value < 0:\n"
        "        raise ValueError('negative input')\n"
        "    counter += 1\n"
        "    return 100 * counter + value\n";
    require(!slot->owner && PyThreadState_Get() == main_state);
    slot->owner = Py_NewInterpreter();
    require(slot->owner != NULL);
    PyObject *scope = PyDict_New();
    require(scope != NULL);
    PyObject *loaded = PyRun_String(source, Py_file_input, scope, scope);
    if (!loaded)
        PyErr_Print();
    require(loaded != NULL);
    Py_DECREF(loaded);
    slot->callback = PyDict_GetItemString(scope, "step");
    require(slot->callback && PyCallable_Check(slot->callback));
    Py_INCREF(slot->callback);
    Py_DECREF(scope);
    slot->generation++;
    PyThreadState_Swap(main_state);
}

static void call(Callback *slot, PyThreadState *main_state, unsigned generation, long input) {
    if (!slot->owner || slot->generation != generation) {
        puts("stale");
        return;
    }
    require(PyThreadState_Get() == main_state);
    PyThreadState_Swap(slot->owner);
    PyObject *argument = PyLong_FromLong(input);
    require(argument != NULL);
    PyObject *result = PyObject_CallOneArg(slot->callback, argument);
    Py_DECREF(argument);
    if (result) {
        long value = PyLong_AsLong(result);
        require(!PyErr_Occurred());
        Py_DECREF(result);
        printf("value:%ld\n", value);
    } else {
        require(PyErr_ExceptionMatches(PyExc_ValueError));
        PyErr_Clear();
        puts("callback-error");
    }
    PyThreadState_Swap(main_state);
}

static void retire(Callback *slot, PyThreadState *main_state) {
    require(slot->owner && PyThreadState_Get() == main_state);
    PyThreadState_Swap(slot->owner);
    Py_DECREF(slot->callback);
    slot->callback = NULL;
    Py_EndInterpreter(slot->owner);
    slot->owner = NULL;
    PyThreadState_Swap(main_state);
}

static void one_cycle(const char *root) {
    start_runtime(root);
    PyThreadState *main_state = PyThreadState_Get();
    Callback a = {0}, b = {0};
    create(&a, main_state);
    create(&b, main_state);
    require(PyThreadState_GetInterpreter(a.owner) != PyThreadState_GetInterpreter(b.owner));
    call(&a, main_state, 1, 4);
    call(&b, main_state, 1, 4);
    call(&a, main_state, 1, -1);
    call(&a, main_state, 1, 6);
    retire(&a, main_state);
    call(&a, main_state, 1, 7);
    create(&a, main_state);
    call(&a, main_state, 1, 7);
    call(&a, main_state, 2, 8);
    call(&b, main_state, 1, 9);
    retire(&a, main_state);
    retire(&b, main_state);
    require(Py_FinalizeEx() == 0);
    puts("finalized");
}

int main(int argc, char **argv) {
    require(argc == 2);
    one_cycle(argv[1]);
    one_cycle(argv[1]);
}
