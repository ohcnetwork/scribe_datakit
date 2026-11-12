// shadcn-style Button / Input, recreated from the CARE UI design tokens.
export function Button({ variant = 'default', size = 'md', icon: Icon, spin, children, ...rest }) {
  const cls = `btn${variant !== 'default' ? ' ' + variant : ''}${size !== 'md' ? ' ' + size : ''}`
  const isz = size === 'lg' ? 17 : 15
  return (
    <button className={cls} {...rest}>
      {Icon && <Icon size={isz} strokeWidth={1.75} className={spin ? 'spin' : undefined} />}
      {children}
    </button>
  )
}

export function Input({ icon: Icon, style, ...rest }) {
  return (
    <span className="input-wrap" style={style}>
      {Icon && <span className="ic"><Icon size={16} strokeWidth={1.75} /></span>}
      <input className={`input${Icon ? ' has-icon' : ''}`} {...rest} />
    </span>
  )
}
