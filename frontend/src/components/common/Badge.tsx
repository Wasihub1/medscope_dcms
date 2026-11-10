import React from 'react';

export type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'orange';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  className?: string;
  dot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  className = '',
  dot = false,
}) => {
  const variantStyles: Record<BadgeVariant, string> = {
    success: 'bg-[#EDF7EE] text-[#1E6327] border-[#C3E6C7]',
    warning: 'bg-[#FEF7EC] text-[#8A5608] border-[#FBE0B2]',
    danger: 'bg-[#FDF2F0] text-[#9C2417] border-[#F8CBC6]',
    info: 'bg-[#EDF5F7] text-[#185B68] border-[#C4E2E7]',
    neutral: 'bg-[#E8E7E3] text-[#54524A] border-[#CAC7BE]',
    orange: 'bg-[#FAF3EC] text-[#96572A] border-[#E6C4A7]',
  };

  const dotColors: Record<BadgeVariant, string> = {
    success: 'bg-[#2D8A39]',
    warning: 'bg-[#D9820B]',
    danger: 'bg-[#D03828]',
    info: 'bg-[#248496]',
    neutral: 'bg-[#8E8A7E]',
    orange: 'bg-[#CF8852]',
  };

  const sizeStyles = {
    sm: 'text-[11px] px-2 py-0.5 gap-1.5',
    md: 'text-xs px-2.5 py-1 gap-1.5',
  }[size];

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full border tracking-wide transition-colors ${variantStyles[variant]} ${sizeStyles} ${className}`}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${dotColors[variant]} shrink-0`} />}
      {children}
    </span>
  );
};

