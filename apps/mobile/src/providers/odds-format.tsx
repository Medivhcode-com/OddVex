import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, use, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import type { OddsFormat } from '@/utils/format';

export const ODDS_FORMAT_KEY = 'oddvex.odds-format';

type OddsFormatValue = { format: OddsFormat; setFormat: (format: OddsFormat) => void };

const OddsFormatContext = createContext<OddsFormatValue>({ format: 'american', setFormat: () => {} });

function isOddsFormat(value: unknown): value is OddsFormat {
  return value === 'american' || value === 'decimal';
}

/** Holds the odds format and persists it on the device. Defaults to American until the stored value is read. */
export function OddsFormatProvider({ children }: { children: ReactNode }) {
  const [format, setFormatState] = useState<OddsFormat>('american');

  useEffect(() => {
    let active = true;
    AsyncStorage.getItem(ODDS_FORMAT_KEY).then(
      (stored) => {
        if (active && isOddsFormat(stored)) setFormatState(stored);
      },
      () => {
        // Storage is unavailable. The default stays in effect for this session.
      },
    );
    return () => {
      active = false;
    };
  }, []);

  const setFormat = useCallback((next: OddsFormat) => {
    setFormatState(next);
    AsyncStorage.setItem(ODDS_FORMAT_KEY, next).catch(() => {
      // The choice still applies for this session; it just will not survive a restart.
    });
  }, []);

  const value = useMemo(() => ({ format, setFormat }), [format, setFormat]);
  return <OddsFormatContext value={value}>{children}</OddsFormatContext>;
}

export function useOddsFormat(): OddsFormatValue {
  return use(OddsFormatContext);
}
