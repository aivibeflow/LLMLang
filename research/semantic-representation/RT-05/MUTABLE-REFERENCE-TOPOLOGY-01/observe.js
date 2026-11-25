"use strict";

const { readFileSync } = require("node:fs");

function observe(graph, recipe) {
    const cells = new Map(graph.cells.map(([id, value]) => [id, {value, next: null}]));
    for (const [id, , next] of graph.cells) {
        cells.get(id).next = next === null ? null : cells.get(next);
    }
    const roots = graph.roots.map(id => cells.get(id));
    function resolve([slot, depth]) {
        let cell = roots[slot];
        for (let step = 0; step < depth && cell !== null; step += 1) cell = cell.next;
        return cell;
    }
    return recipe.map(([operation, path, argument]) => {
        const cell = resolve(path);
        if (operation === "same") {
            const right = resolve(argument);
            return cell !== null && right !== null && cell === right;
        }
        if (cell === null) return null;
        if (operation === "add") cell.value += argument;
        if (operation === "link") {
            cell.next = resolve(argument);
            return cell.next !== null;
        }
        if (operation === "read" || operation === "add") return cell.value;
        throw new Error(`Unknown operation ${operation}`);
    });
}

const { graphs, recipes } = JSON.parse(readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(graphs.map(graph => recipes.map(recipe => observe(graph, recipe)))));
