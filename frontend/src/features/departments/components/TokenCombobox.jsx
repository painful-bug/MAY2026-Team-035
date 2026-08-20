import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Plus, X } from 'lucide-react';

// **One component, because skills and categories are one problem.**
//
// Both fields exist to stop somebody typing "Plumbling" beside "Plumbing", and
// both solve it the same way: show the closest matches first, and only offer to
// create when nothing matches exactly. Building two would mean the duplicate
// prevention had two implementations, and the second one to be edited would be
// the one that quietly stopped matching.
//
// What differs between the two callers is data, not behaviour, so it is passed
// in: where suggestions come from, whether an exact match exists, and what a
// row says underneath its name.
//
// THE RULE THIS COMPONENT EXISTS TO ENFORCE
//
// `isExact` is **never computed here.** It arrives from Postgres, where the
// comparison is `lower(btrim(a)) = lower(btrim(b))` against the stored value. A
// second implementation in the browser would agree on almost every input and
// disagree on exactly the ones that matter — a trailing space, a different
// capitalisation — and disagreeing means offering to create a duplicate of
// something that already exists. So the "add" row is shown when the *server*
// says no exact match, and never when it says there is one.

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs ' +
  'font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';

/**
 * A text box that suggests, and offers to create only when nothing matches.
 *
 * @param {object}   props
 * @param {string}   props.label
 * @param {Array}    props.selected      `{ id, name }`, rendered as removable chips.
 * @param {Array}    props.suggestions   `{ id, name, isExact?, detail?, warning? }`.
 * @param {boolean}  props.hasExactMatch Whether the server matched the query exactly.
 * @param {boolean}  props.isLoading
 * @param {string}   props.query
 * @param {Function} props.onQueryChange
 * @param {Function} props.onSelect      An existing row was chosen.
 * @param {Function} props.onCreate      The "add" row was chosen. Gets the raw query.
 * @param {Function} props.onRemove      A chip's × was pressed.
 * @param {string}   [props.placeholder]
 * @param {string}   [props.addLabel]    Verb for the create row. "skill" → `Add "x" as a new skill`.
 * @param {boolean}  [props.busy]        A create is in flight; the add row is disabled.
 * @param {string}   [props.error]
 */
export default function TokenCombobox({
  label,
  selected = [],
  suggestions = [],
  hasExactMatch = false,
  isLoading = false,
  query,
  onQueryChange,
  onSelect,
  onCreate,
  onRemove,
  placeholder = 'Start typing…',
  addLabel = 'entry',
  busy = false,
  error = '',
  required = false,
}) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrapperRef = useRef(null);

  const typed = query.trim();
  const chosenIds = useMemo(
    () => new Set(selected.map((entry) => entry.id)),
    [selected]
  );

  // Already-chosen rows are filtered out rather than shown greyed: this list is
  // short and a disabled row in it is a row somebody tries to click.
  const rows = suggestions.filter((entry) => !chosenIds.has(entry.id));

  // The create row appears only when the server found no exact match *and* the
  // typed name is not already a chip. The second half matters because a chip is
  // filtered out of `rows` above, so without it, adding "Plumbing" and typing
  // it again would offer to create a second one.
  const alreadyChosen = selected.some(
    (entry) => entry.name.trim().toLowerCase() === typed.toLowerCase()
  );
  const canCreate = Boolean(typed) && !hasExactMatch && !alreadyChosen && !isLoading;
  const options = canCreate ? [...rows, { id: '__create__' }] : rows;

  useEffect(() => {
    setActive(0);
  }, [query, suggestions.length]);

  useEffect(() => {
    const onClickAway = (event) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onClickAway);
    return () => document.removeEventListener('mousedown', onClickAway);
  }, []);

  const choose = (option) => {
    if (!option) return;
    if (option.id === '__create__') {
      onCreate(typed);
    } else {
      onSelect(option);
    }
    onQueryChange('');
    setOpen(false);
  };

  const onKeyDown = (event) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!options.length) return;
      setOpen(true);
      setActive((current) => {
        const next = event.key === 'ArrowDown' ? current + 1 : current - 1;
        return (next + options.length) % options.length;
      });
      return;
    }
    if (event.key === 'Enter') {
      // Only when the list is open with something highlighted. Otherwise Enter
      // belongs to the form, and swallowing it here would make the field feel
      // broken to anyone who never opened the list.
      if (open && options.length) {
        event.preventDefault();
        choose(options[active]);
      }
      return;
    }
    if (event.key === 'Escape') {
      setOpen(false);
    }
  };

  // NOT a wrapping <label>: a label forwards any click inside it to its first
  // labelable descendant, and once a chip exists that descendant is the first
  // chip's × button — so clicking blank space anywhere in the field silently
  // removed chips one by one. htmlFor keeps the caption-click-focuses-input
  // behaviour, which was the only thing the wrapper was buying.
  return (
    <div className="block space-y-1.5" ref={wrapperRef}>
      <label
        htmlFor={`${listId}-input`}
        className="text-[10px] font-bold uppercase tracking-wider text-slate-400"
      >
        {label}
        {required ? <span className="ml-0.5 text-rose-500">*</span> : null}
      </label>

      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pb-1">
          {selected.map((entry) => (
            <span
              key={entry.id}
              className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-1 text-[10px] font-bold text-indigo-700"
            >
              {entry.name}
              <button
                type="button"
                onClick={() => onRemove(entry)}
                className="rounded-full p-0.5 hover:bg-indigo-100"
                aria-label={`Remove ${entry.name}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="relative">
        <input
          id={`${listId}-input`}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={
            open && options[active] ? `${listId}-${active}` : undefined
          }
          value={query}
          placeholder={placeholder}
          onChange={(event) => {
            onQueryChange(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className={inputClass}
        />

        {open && (typed || rows.length > 0) && (
          <ul
            id={listId}
            role="listbox"
            className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-xl border border-slate-200 bg-white py-1 shadow-lg"
          >
            {isLoading && (
              <li className="px-3 py-2 text-[11px] font-semibold text-slate-400">
                Searching…
              </li>
            )}

            {!isLoading && options.length === 0 && (
              <li className="px-3 py-2 text-[11px] font-semibold text-slate-400">
                No matches.
              </li>
            )}

            {options.map((option, index) =>
              option.id === '__create__' ? (
                <li key="__create__" id={`${listId}-${index}`} role="option" aria-selected={index === active}>
                  <button
                    type="button"
                    disabled={busy}
                    onMouseEnter={() => setActive(index)}
                    onClick={() => choose(option)}
                    className={`flex w-full items-center gap-2 px-3 py-2 text-left text-[11px] font-bold text-emerald-700 disabled:opacity-50 ${
                      index === active ? 'bg-emerald-50' : ''
                    }`}
                  >
                    <Plus className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">
                      {busy ? 'Adding…' : `Add “${typed}” as a new ${addLabel}`}
                    </span>
                  </button>
                </li>
              ) : (
                <li key={option.id} id={`${listId}-${index}`} role="option" aria-selected={index === active}>
                  <button
                    type="button"
                    onMouseEnter={() => setActive(index)}
                    onClick={() => choose(option)}
                    className={`block w-full px-3 py-2 text-left ${
                      index === active ? 'bg-slate-50' : ''
                    }`}
                  >
                    <span className="block text-[11px] font-bold text-slate-700">
                      {option.name}
                    </span>
                    {option.detail ? (
                      <span
                        className={`block text-[10px] font-semibold ${
                          option.warning ? 'text-amber-600' : 'text-slate-400'
                        }`}
                      >
                        {option.detail}
                      </span>
                    ) : null}
                  </button>
                </li>
              )
            )}
          </ul>
        )}
      </div>

      {/* The closest matches stay visible above the add row rather than being
          replaced by it — that ordering IS the duplicate prevention. Somebody
          typing "Plumbling" sees "Plumbing" before they see the offer to
          create, which is the only moment they will notice. */}
      {error ? (
        <p role="alert" className="text-[10px] font-semibold text-rose-600">
          {error}
        </p>
      ) : null}
    </div>
  );
}
