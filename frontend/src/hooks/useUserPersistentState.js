import { useCallback, useEffect, useMemo, useState } from 'react';

function resolveInitialValue(initialValue) {
  return typeof initialValue === 'function' ? initialValue() : initialValue;
}

export default function useUserPersistentState(userStorageKey, namespace, initialValue) {
  const [initial] = useState(() => resolveInitialValue(initialValue));

  const readFromStorage = useCallback((key) => {
    try {
      const raw = localStorage.getItem(key);
      if (raw == null) return initial;
      return JSON.parse(raw);
    } catch {
      return initial;
    }
  }, [initial]);

  const scopedStorageKey = useMemo(() => {
    const scope = userStorageKey || 'guest';
    return `auto_rpa:${scope}:${namespace}`;
  }, [userStorageKey, namespace]);

  const [state, setState] = useState(() => {
    return readFromStorage(scopedStorageKey);
  });

  useEffect(() => {
    setState(readFromStorage(scopedStorageKey));
  }, [readFromStorage, scopedStorageKey]);

  useEffect(() => {
    try {
      localStorage.setItem(scopedStorageKey, JSON.stringify(state));
    } catch {
      // Ignore localStorage quota/private mode errors.
    }
  }, [scopedStorageKey, state]);

  return [state, setState];
}