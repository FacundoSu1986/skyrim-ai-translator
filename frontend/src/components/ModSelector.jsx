import { useEffect, useRef, useState } from 'react';

export function ModSelector({ modsList = [], selectedMod = '', onSelectMod, disabled = false }) {
  const [isOpen, setIsOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const containerRef = useRef(null);
  const buttonRef = useRef(null);
  const listRef = useRef(null);

  const selectedIndex = modsList.indexOf(selectedMod);

  // Sync focused index when opening or when selectedMod changes
  useEffect(() => {
    if (isOpen) {
      setFocusedIndex(selectedIndex >= 0 ? selectedIndex : 0);
    }
  }, [isOpen, selectedIndex]);

  // Click outside to close
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Scroll focused option into view
  useEffect(() => {
    if (isOpen && focusedIndex >= 0 && listRef.current) {
      const optionEl = listRef.current.children[focusedIndex];
      if (optionEl && typeof optionEl.scrollIntoView === 'function') {
        optionEl.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [focusedIndex, isOpen]);

  const handleToggle = () => {
    if (disabled || modsList.length === 0) return;
    setIsOpen((prev) => !prev);
  };

  const handleSelect = (mod) => {
    if (disabled) return;
    onSelectMod(mod);
    setIsOpen(false);
    buttonRef.current?.focus();
  };

  const handleKeyDown = (event) => {
    if (disabled || modsList.length === 0) return;

    switch (event.key) {
      case 'ArrowDown': {
        event.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
          setFocusedIndex(selectedIndex >= 0 ? selectedIndex : 0);
        } else {
          setFocusedIndex((prev) => (prev < modsList.length - 1 ? prev + 1 : 0));
        }
        break;
      }
      case 'ArrowUp': {
        event.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
          setFocusedIndex(selectedIndex >= 0 ? selectedIndex : modsList.length - 1);
        } else {
          setFocusedIndex((prev) => (prev > 0 ? prev - 1 : modsList.length - 1));
        }
        break;
      }
      case 'Home': {
        if (isOpen) {
          event.preventDefault();
          setFocusedIndex(0);
        }
        break;
      }
      case 'End': {
        if (isOpen) {
          event.preventDefault();
          setFocusedIndex(modsList.length - 1);
        }
        break;
      }
      case 'Enter':
      case ' ': {
        event.preventDefault();
        if (isOpen && focusedIndex >= 0 && focusedIndex < modsList.length) {
          handleSelect(modsList[focusedIndex]);
        } else {
          setIsOpen(true);
        }
        break;
      }
      case 'Escape': {
        if (isOpen) {
          event.preventDefault();
          setIsOpen(false);
          buttonRef.current?.focus();
        }
        break;
      }
      case 'Tab': {
        if (isOpen) {
          setIsOpen(false);
        }
        break;
      }
      default:
        break;
    }
  };

  if (modsList.length === 0) {
    return (
      <div className="hint-box">
        No se encontraron mods. Introduce la ruta de MO2 y usa <strong>ESCANEAR</strong>.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`mod-selector-wrapper ${isOpen ? 'open' : ''} ${disabled ? 'disabled' : ''}`}
      onKeyDown={handleKeyDown}
    >
      <button
        ref={buttonRef}
        id="mod-select-button"
        type="button"
        className="mod-selector-trigger"
        onClick={handleToggle}
        disabled={disabled}
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls="mod-select-listbox"
        aria-labelledby="mod-select-label mod-select-button"
        aria-activedescendant={
          isOpen && focusedIndex >= 0 ? `mod-option-${focusedIndex}` : undefined
        }
      >
        <span className="field-icon sword-icon" aria-hidden="true">
          ⚔
        </span>
        <span className="mod-selector-value">
          {selectedMod || 'Selecciona un mod...'}
        </span>
        <span className="mod-selector-arrow" aria-hidden="true">
          {isOpen ? '▲' : '▼'}
        </span>
      </button>

      {isOpen && (
        <ul
          ref={listRef}
          id="mod-select-listbox"
          className="mod-selector-listbox"
          role="listbox"
          aria-labelledby="mod-select-label"
          tabIndex={-1}
        >
          {modsList.map((mod, index) => {
            const isSelected = mod === selectedMod;
            const isFocused = index === focusedIndex;
            return (
              <li
                key={mod}
                id={`mod-option-${index}`}
                role="option"
                aria-selected={isSelected}
                className={`mod-selector-option ${isSelected ? 'selected' : ''} ${
                  isFocused ? 'focused' : ''
                }`}
                onClick={() => handleSelect(mod)}
                onMouseEnter={() => setFocusedIndex(index)}
              >
                <span className="option-marker" aria-hidden="true">
                  {isSelected ? '◆' : '◇'}
                </span>
                <span className="option-name">{mod}</span>
                {isSelected && (
                  <span className="option-check" aria-hidden="true">
                    ✓
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default ModSelector;
