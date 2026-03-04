# Patterns by Language

Language-specific refinements for simplification patterns. Auto-detect based on file extensions in scope.

## TypeScript / JavaScript

### Deletion
- Unused imports (check with `tsc --noEmit` or ESLint)
- Unused variables (especially in destructuring)
- Type-only imports that could use `import type`

### Flattening
- Unnecessary `async` on functions that don't await
- Promise chains that could be async/await (or vice versa if simpler)
- Nested ternaries → early returns or switch

### Derivation (React-specific)
- `useState` for values derivable from props or other state
- `useEffect` for synchronous computations (should be inline or useMemo)
- Context for shallow prop drilling (2-3 levels)

### Consolidation
- Duplicate utility functions across files
- Similar React components with minor prop differences
- Repeated validation logic

## Python

### Deletion
- Unused imports (check with `ruff` or `flake8`)
- Variables assigned but never read
- `pass` statements in non-empty blocks

### Flattening
- Nested `if` statements → combined conditions or early returns
- `try/except` blocks that just re-raise
- Unnecessary list comprehensions for simple iteration

### Derivation
- Cached properties that could use `@property`
- Instance variables recomputed from other instance variables

### Consolidation
- Similar functions differing only in one parameter
- Repeated dict/list transformations

## Go

### Deletion
- Unused imports (enforced by compiler, but check for underscore imports)
- Unused struct fields
- Empty `else` blocks

### Flattening
- Nested `if err != nil` → early returns
- Unnecessary type assertions when interface is sufficient

### Derivation
- Struct fields storing derived data that could be methods

### Consolidation
- Similar functions that could be generics (Go 1.18+)
- Repeated error wrapping patterns

## General (All Languages)

### Deletion
- Commented-out code (if >1 week old in git history)
- TODO comments with no issue reference
- Debug print statements

### Flattening
- Functions that just call another function with same args
- Classes with single method (could be function)
- Excessive null checks on values that can't be null

### Derivation
- Caches without invalidation (often a bug source)
- Flags that mirror other state

### Consolidation
- Copy-paste code blocks with minor variations
- Similar error messages that could be templated
