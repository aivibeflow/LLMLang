#!/bin/sh
# Run Vellvm's extracted bytecode from a prepared opam switch.
set -eu
exec "${OCAMLRUN:-ocamlrun}" "${VELLVM_BYTECODE:?Set VELLVM_BYTECODE to Vellvm main.bc}" "$@"
