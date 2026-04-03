export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      keyframes: {
        'slide-in': { from: { transform: 'translateX(100%)' }, to: { transform: 'translateX(0)' } }
      },
      animation: {
        'slide-in': 'slide-in 0.25s ease-out'
      }
    }
  },
  plugins: []
}
