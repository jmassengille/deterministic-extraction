import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import PropTypes from 'prop-types'

export default function GlassCard({ children, className, hover = true, ...props }) {
  return (
    <motion.div
      className={clsx(
        'relative rounded-2xl p-6',
        'bg-white/5 backdrop-blur-md',
        'border border-white/10',
        'shadow-[0_8px_32px_rgba(0,0,0,0.3)]',
        hover && 'transition-all duration-300',
        className
      )}
      whileHover={hover ? {
        scale: 1.02,
        borderColor: 'rgba(0, 102, 204, 0.5)',
        boxShadow: '0 12px 48px rgba(0, 102, 204, 0.2)'
      } : undefined}
      {...props}
    >
      {children}
    </motion.div>
  )
}

GlassCard.propTypes = {
  children: PropTypes.node.isRequired,
  className: PropTypes.string,
  hover: PropTypes.bool
}
