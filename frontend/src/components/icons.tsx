import type { JSX, ReactNode, SVGProps } from "react";

export type IconProps = SVGProps<SVGSVGElement>;

function IconBase({ className, children, ...props }: IconProps & { children: ReactNode }): JSX.Element {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {children}
    </svg>
  );
}

export function WrenchIcon({ className, ...props }: IconProps): JSX.Element {
  return (
    <IconBase className={className} {...props}>
      <path d="M21 6.5h-3l-3-3-3 3 2 2-8 8a2.1 2.1 0 1 0 3 3l8-8 2 2 3-3-2-2Z" />
      <line x1="11" y1="13" x2="13" y2="15" />
    </IconBase>
  );
}

export function MailIcon({ className, ...props }: IconProps): JSX.Element {
  return (
    <IconBase className={className} {...props}>
      <rect x="3" y="5" width="18" height="14" rx="2.2" />
      <path d="m3 7 9 6 9-6" />
    </IconBase>
  );
}

export function SearchIcon({ className, ...props }: IconProps): JSX.Element {
  return (
    <IconBase className={className} {...props}>
      <circle cx="11" cy="11" r="5.5" />
      <path d="m15.8 15.8 4.2 4.2" />
    </IconBase>
  );
}

export function ClipboardListIcon({ className, ...props }: IconProps): JSX.Element {
  return (
    <IconBase className={className} {...props}>
      <rect x="5.5" y="4.5" width="13" height="16" rx="2.5" />
      <path d="M9 2.8h6" />
      <path d="M12 2.8v1.7" />
      <path d="M9 9h6" />
      <path d="M9 13h6" />
      <circle cx="7.1" cy="9" r="0.6" />
      <circle cx="7.1" cy="13" r="0.6" />
    </IconBase>
  );
}

export function SparklesIcon({ className, ...props }: IconProps): JSX.Element {
  return (
    <IconBase className={className} {...props}>
      <path d="M12 4.2 13.1 7.6 16.5 8.7 13.1 9.8 12 13.2 10.9 9.8 7.5 8.7 10.9 7.6 12 4.2Z" />
      <path d="M6.5 4.8 7 6.3 8.5 6.8 7 7.3 6.5 8.8 6 7.3 4.5 6.8 6 6.3 6.5 4.8Z" />
      <path d="M17.5 13.2 18 14.7 19.5 15.2 18 15.7 17.5 17.2 17 15.7 15.5 15.2 17 14.7 17.5 13.2Z" />
    </IconBase>
  );
}

