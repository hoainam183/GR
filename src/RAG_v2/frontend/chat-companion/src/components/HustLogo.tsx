import hustLogoSrc from '/hust-logo.png';

interface HustLogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

const sizeMap = {
  sm: 'h-6 w-6',
  md: 'h-8 w-8',
  lg: 'h-10 w-10',
  xl: 'h-16 w-16',
};

const HustLogo = ({ size = 'md', className = '' }: HustLogoProps) => (
  <img
    src="/hust-logo.png"
    alt="ĐHBK Hà Nội"
    className={`${sizeMap[size]} object-contain ${className}`}
  />
);

export default HustLogo;
