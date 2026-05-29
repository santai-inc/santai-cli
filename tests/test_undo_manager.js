/**
 * Unit tests for UndoManager — run with: node tests/test_undo_manager.js
 *
 * Tests the stack-based undo/redo state management logic in isolation.
 * No DOM or fetch dependencies.
 */

// ---------------------------------------------------------------------------
// Inline UndoManager (mirrors the class in index.html)
// ---------------------------------------------------------------------------

class UndoManager {
    constructor(maxHistory = 50) {
        this._stack = [];
        this._redoStack = [];
        this._maxHistory = maxHistory;
        this._onChange = null;
    }
    _notify() { if (this._onChange) this._onChange(); }
    push(op) {
        this._stack.push(op);
        if (this._stack.length > this._maxHistory) this._stack.shift();
        this._redoStack = [];
        this._notify();
    }
    pop() { const op = this._stack.pop() || null; this._notify(); return op; }
    pushRedo(op) {
        this._redoStack.push(op);
        if (this._redoStack.length > this._maxHistory) this._redoStack.shift();
        this._notify();
    }
    popRedo() { const op = this._redoStack.pop() || null; this._notify(); return op; }
    pushFromRedo(op) {
        this._stack.push(op);
        if (this._stack.length > this._maxHistory) this._stack.shift();
        this._notify();
    }
    canUndo() { return this._stack.length > 0; }
    canRedo() { return this._redoStack.length > 0; }
    peek() { return this._stack[this._stack.length - 1] || null; }
    clear() { this._stack = []; this._redoStack = []; this._notify(); }
    get size() { return this._stack.length; }
}

// ---------------------------------------------------------------------------
// Minimal test runner
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;

function test(name, fn) {
    try {
        fn();
        console.log(`  PASS  ${name}`);
        passed++;
    } catch (err) {
        console.error(`  FAIL  ${name}`);
        console.error(`        ${err.message}`);
        failed++;
    }
}

function assert(condition, msg) {
    if (!condition) throw new Error(msg || 'Assertion failed');
}

function assertEqual(actual, expected, msg) {
    if (actual !== expected) {
        throw new Error(msg || `Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    }
}

// ---------------------------------------------------------------------------
// Tests: initial state
// ---------------------------------------------------------------------------

console.log('\nUndoManager — initial state');

test('canUndo() is false when empty', () => {
    const um = new UndoManager();
    assert(!um.canUndo(), 'should not be undoable when empty');
});

test('canRedo() is false when empty', () => {
    const um = new UndoManager();
    assert(!um.canRedo(), 'should not be redoable when empty');
});

test('size is 0 when empty', () => {
    const um = new UndoManager();
    assertEqual(um.size, 0);
});

test('pop() returns null when empty', () => {
    const um = new UndoManager();
    assertEqual(um.pop(), null);
});

test('popRedo() returns null when empty', () => {
    const um = new UndoManager();
    assertEqual(um.popRedo(), null);
});

test('peek() returns null when empty', () => {
    const um = new UndoManager();
    assertEqual(um.peek(), null);
});

// ---------------------------------------------------------------------------
// Tests: push and pop
// ---------------------------------------------------------------------------

console.log('\nUndoManager — push and pop');

test('canUndo() is true after push', () => {
    const um = new UndoManager();
    um.push({ type: 'RENAME', label: 'Rename "a" to "b"' });
    assert(um.canUndo());
});

test('size increments with each push', () => {
    const um = new UndoManager();
    um.push({ type: 'SAVE' });
    um.push({ type: 'MOVE' });
    assertEqual(um.size, 2);
});

test('pop returns last pushed operation', () => {
    const um = new UndoManager();
    const op1 = { type: 'SAVE', label: 'Edit "file.md"' };
    const op2 = { type: 'RENAME', label: 'Rename "a" to "b"' };
    um.push(op1);
    um.push(op2);
    assertEqual(um.pop(), op2);
});

test('pop removes the operation (LIFO)', () => {
    const um = new UndoManager();
    um.push({ type: 'SAVE' });
    um.push({ type: 'MOVE' });
    um.pop();
    assertEqual(um.size, 1);
});

test('canUndo() is false after popping all operations', () => {
    const um = new UndoManager();
    um.push({ type: 'SAVE' });
    um.pop();
    assert(!um.canUndo());
});

test('peek returns last operation without removing it', () => {
    const um = new UndoManager();
    const op = { type: 'MOVE', label: 'Move "x.md"' };
    um.push(op);
    assertEqual(um.peek(), op);
    assertEqual(um.size, 1, 'peek should not remove the operation');
});

// ---------------------------------------------------------------------------
// Tests: redo stack
// ---------------------------------------------------------------------------

console.log('\nUndoManager — redo stack');

test('canRedo() is true after pushRedo', () => {
    const um = new UndoManager();
    um.pushRedo({ type: 'SAVE', label: 'Edit "foo.md"' });
    assert(um.canRedo());
});

test('popRedo returns last pushed redo operation', () => {
    const um = new UndoManager();
    const op1 = { type: 'SAVE', label: 'first' };
    const op2 = { type: 'RENAME', label: 'second' };
    um.pushRedo(op1);
    um.pushRedo(op2);
    assertEqual(um.popRedo(), op2);
});

test('popRedo removes the redo operation', () => {
    const um = new UndoManager();
    um.pushRedo({ type: 'SAVE' });
    um.popRedo();
    assert(!um.canRedo());
});

test('push() clears the redo stack', () => {
    const um = new UndoManager();
    um.pushRedo({ type: 'SAVE', label: 'undone op' });
    assert(um.canRedo(), 'redo should be available before push');
    um.push({ type: 'DELETE', label: 'new action' });
    assert(!um.canRedo(), 'new user action should clear redo history');
});

test('pushFromRedo() adds to undo stack without clearing redo stack', () => {
    const um = new UndoManager();
    um.pushRedo({ type: 'MOVE', label: 'next redo' });
    um.pushFromRedo({ type: 'SAVE', label: 'restored op' });
    assert(um.canUndo(), 'undo stack should have the restored op');
    assert(um.canRedo(), 'redo stack should be preserved');
});

test('redo stack respects maxHistory cap', () => {
    const um = new UndoManager(3);
    for (let i = 0; i < 5; i++) um.pushRedo({ type: 'SAVE', label: `op-${i}` });
    let count = 0;
    while (um.canRedo()) { um.popRedo(); count++; }
    assert(count <= 3, `redo stack had ${count} entries, expected <= 3`);
});

// ---------------------------------------------------------------------------
// Tests: operation payloads
// ---------------------------------------------------------------------------

console.log('\nUndoManager — operation payloads');

test('SAVE operation stores path and previousContent', () => {
    const um = new UndoManager();
    const op = { type: 'SAVE', path: 'notes/foo.md', previousContent: 'hello', label: 'Edit "foo.md"' };
    um.push(op);
    const popped = um.pop();
    assertEqual(popped.type, 'SAVE');
    assertEqual(popped.path, 'notes/foo.md');
    assertEqual(popped.previousContent, 'hello');
});

test('MOVE operation stores moves array with originalParent and newPath', () => {
    const um = new UndoManager();
    const op = {
        type: 'MOVE',
        moves: [{ originalPath: 'a/f.md', originalParent: 'a', itemName: 'f.md', newPath: 'b/f.md' }],
        label: 'Move "f.md" to b'
    };
    um.push(op);
    const popped = um.pop();
    assertEqual(popped.moves[0].originalParent, 'a');
    assertEqual(popped.moves[0].newPath, 'b/f.md');
});

test('RENAME operation stores originalName, newName, newPath', () => {
    const um = new UndoManager();
    const op = {
        type: 'RENAME',
        originalPath: 'docs/old.md',
        originalName: 'old.md',
        newName: 'new.md',
        newPath: 'docs/new.md',
        parentFolder: 'docs',
        label: 'Rename "old.md" to "new.md"'
    };
    um.push(op);
    const popped = um.pop();
    assertEqual(popped.originalName, 'old.md');
    assertEqual(popped.newPath, 'docs/new.md');
});

test('CREATE_FILE operation stores created path', () => {
    const um = new UndoManager();
    const op = { type: 'CREATE_FILE', path: 'notes/new.md', label: 'New file "new.md"' };
    um.push(op);
    const popped = um.pop();
    assertEqual(popped.type, 'CREATE_FILE');
    assertEqual(popped.path, 'notes/new.md');
});

test('CREATE_FOLDER operation stores created path', () => {
    const um = new UndoManager();
    const op = { type: 'CREATE_FOLDER', path: 'projects/new-dir', label: 'New folder "new-dir"' };
    um.push(op);
    assertEqual(um.pop().path, 'projects/new-dir');
});

// ---------------------------------------------------------------------------
// Tests: history cap
// ---------------------------------------------------------------------------

console.log('\nUndoManager — history cap');

test('enforces maxHistory limit by evicting the oldest entry', () => {
    const um = new UndoManager(3);
    um.push({ type: 'SAVE', label: 'first' });
    um.push({ type: 'SAVE', label: 'second' });
    um.push({ type: 'SAVE', label: 'third' });
    um.push({ type: 'SAVE', label: 'fourth' }); // evicts 'first'
    assertEqual(um.size, 3);
    const labels = [um.pop().label, um.pop().label, um.pop().label];
    assert(!labels.includes('first'), 'oldest entry should have been evicted');
    assert(labels.includes('second'));
    assert(labels.includes('third'));
    assert(labels.includes('fourth'));
});

test('size never exceeds maxHistory', () => {
    const um = new UndoManager(5);
    for (let i = 0; i < 20; i++) um.push({ type: 'SAVE', label: `op-${i}` });
    assert(um.size <= 5, `size ${um.size} should be <= 5`);
});

// ---------------------------------------------------------------------------
// Tests: clear
// ---------------------------------------------------------------------------

console.log('\nUndoManager — clear');

test('clear() empties the undo stack', () => {
    const um = new UndoManager();
    um.push({ type: 'SAVE' });
    um.push({ type: 'MOVE' });
    um.clear();
    assertEqual(um.size, 0);
    assert(!um.canUndo());
});

test('clear() empties the redo stack', () => {
    const um = new UndoManager();
    um.pushRedo({ type: 'SAVE' });
    um.clear();
    assert(!um.canRedo(), 'clear should also wipe redo stack');
});

// ---------------------------------------------------------------------------
// Tests: _onChange callback
// ---------------------------------------------------------------------------

console.log('\nUndoManager — _onChange callback');

test('_onChange fires on push()', () => {
    const um = new UndoManager();
    let calls = 0;
    um._onChange = () => calls++;
    um.push({ type: 'SAVE' });
    assertEqual(calls, 1);
});

test('_onChange fires on pop()', () => {
    const um = new UndoManager();
    um.push({ type: 'SAVE' });
    let calls = 0;
    um._onChange = () => calls++;
    um.pop();
    assertEqual(calls, 1);
});

test('_onChange fires on pushRedo()', () => {
    const um = new UndoManager();
    let calls = 0;
    um._onChange = () => calls++;
    um.pushRedo({ type: 'SAVE' });
    assertEqual(calls, 1);
});

test('_onChange fires on popRedo()', () => {
    const um = new UndoManager();
    um.pushRedo({ type: 'SAVE' });
    let calls = 0;
    um._onChange = () => calls++;
    um.popRedo();
    assertEqual(calls, 1);
});

test('_onChange fires on pushFromRedo()', () => {
    const um = new UndoManager();
    let calls = 0;
    um._onChange = () => calls++;
    um.pushFromRedo({ type: 'SAVE' });
    assertEqual(calls, 1);
});

test('_onChange fires on clear()', () => {
    const um = new UndoManager();
    um.push({ type: 'SAVE' });
    let calls = 0;
    um._onChange = () => calls++;
    um.clear();
    assertEqual(calls, 1);
});

test('_onChange receives correct canUndo/canRedo state at call time', () => {
    const um = new UndoManager();
    let seenCanUndo = null;
    let seenCanRedo = null;
    um._onChange = () => {
        seenCanUndo = um.canUndo();
        seenCanRedo = um.canRedo();
    };
    um.push({ type: 'SAVE' });
    assert(seenCanUndo === true, 'canUndo should be true inside onChange after push');
    assert(seenCanRedo === false, 'canRedo should be false inside onChange after push (redo cleared)');
});

test('_onChange not called when null', () => {
    const um = new UndoManager();
    um._onChange = null;
    // Should not throw
    um.push({ type: 'SAVE' });
    um.pop();
    um.clear();
});

// ---------------------------------------------------------------------------
// Tests: full undo/redo cycle
// ---------------------------------------------------------------------------

console.log('\nUndoManager — full undo/redo cycle');

test('undo then redo restores original state', () => {
    const um = new UndoManager();
    const op = { type: 'RENAME', label: 'Rename "a" to "b"' };
    um.push(op);

    // Simulate undo: pop from undo, push to redo
    const undone = um.pop();
    um.pushRedo(undone);
    assert(!um.canUndo(), 'undo stack should be empty after undo');
    assert(um.canRedo(), 'redo stack should have the op');

    // Simulate redo: pop from redo, push back to undo via pushFromRedo
    const redone = um.popRedo();
    um.pushFromRedo(redone);
    assert(um.canUndo(), 'undo stack should have op back after redo');
    assert(!um.canRedo(), 'redo stack should be empty after redo');
    assertEqual(um.peek(), op);
});

test('new action after undo discards redo history', () => {
    const um = new UndoManager();
    um.push({ type: 'SAVE', label: 'original' });

    const undone = um.pop();
    um.pushRedo(undone);
    assert(um.canRedo());

    um.push({ type: 'DELETE', label: 'new action' });
    assert(!um.canRedo(), 'redo history should be gone after new user action');
    assert(um.canUndo());
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

console.log(`\n${passed + failed} tests: ${passed} passed, ${failed} failed\n`);
if (failed > 0) process.exit(1);
