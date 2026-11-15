import type { TextProps } from 'react-native';

import type { PriceT } from '@/api/types';
import { Num, type Tone } from '@/components/text';
import { useOddsFormat } from '@/providers/odds-format';
import { formatPrice } from '@/utils/format';

/** A price in the format chosen in Settings. Both formats come from the API; nothing is converted here. */
export function Price({ price, tone, size, ...rest }: TextProps & { price: PriceT; tone?: Tone; size?: number }) {
  const { format } = useOddsFormat();
  return (
    <Num tone={tone} size={size} {...rest}>
      {formatPrice(price, format)}
    </Num>
  );
}
