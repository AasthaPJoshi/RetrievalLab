import { useCountUp } from '@/hooks/useCountUp';

interface CountUpProps {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  duration?: number;
}

export function CountUp({ value, decimals = 0, prefix = '', suffix = '', className, duration }: CountUpProps) {
  const { ref, display } = useCountUp(value, { decimals, duration });
  return (
    <span ref={ref} className={className}>
      {prefix}{display}{suffix}
    </span>
  );
}
