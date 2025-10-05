// Hero Slider Component
class HeroSlider {
  constructor(containerSelector) {
    this.container = document.querySelector(containerSelector);
    if (!this.container) return;

    this.slides = this.container.querySelectorAll('.hero-slide');
    this.dots = this.container.querySelectorAll('.hero-dot');
    this.prevBtn = this.container.querySelector('.hero-arrow.prev');
    this.nextBtn = this.container.querySelector('.hero-arrow.next');
    
    // Only initialize if we have slides
    if (this.slides.length === 0) return;
    
    this.currentSlide = 0;
    this.autoSlideInterval = null;
    this.isPlaying = true;
    this.touchStartX = 0;
    this.touchEndX = 0;

    this.init();
  }

  init() {
    this.setupEventListeners();
    this.showSlide(0);
    this.startAutoSlide();
    this.setupTouchEvents();
    this.setupKeyboardEvents();
  }

  setupEventListeners() {
    // Navigation buttons
    if (this.prevBtn) {
      this.prevBtn.addEventListener('click', () => this.prevSlide());
    }
    
    if (this.nextBtn) {
      this.nextBtn.addEventListener('click', () => this.nextSlide());
    }

    // Dots navigation
    this.dots.forEach((dot, index) => {
      dot.addEventListener('click', () => this.goToSlide(index));
    });

    // Pause on hover
    this.container.addEventListener('mouseenter', () => this.pauseAutoSlide());
    this.container.addEventListener('mouseleave', () => this.resumeAutoSlide());

    // Pause when tab is not visible
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.pauseAutoSlide();
      } else {
        this.resumeAutoSlide();
      }
    });
  }

  setupTouchEvents() {
    this.container.addEventListener('touchstart', (e) => {
      this.touchStartX = e.changedTouches[0].screenX;
      this.pauseAutoSlide();
    }, { passive: true });

    this.container.addEventListener('touchend', (e) => {
      this.touchEndX = e.changedTouches[0].screenX;
      this.handleSwipe();
      this.resumeAutoSlide();
    }, { passive: true });
  }

  setupKeyboardEvents() {
    document.addEventListener('keydown', (e) => {
      if (!this.isInViewport()) return;

      switch (e.key) {
        case 'ArrowLeft':
          e.preventDefault();
          this.prevSlide();
          break;
        case 'ArrowRight':
          e.preventDefault();
          this.nextSlide();
          break;
        case ' ':
          e.preventDefault();
          this.toggleAutoSlide();
          break;
      }
    });
  }

  handleSwipe() {
    const swipeThreshold = 50;
    const swipeDistance = this.touchEndX - this.touchStartX;
    
    if (Math.abs(swipeDistance) > swipeThreshold) {
      if (swipeDistance > 0) {
        this.prevSlide();
      } else {
        this.nextSlide();
      }
    }
  }

  showSlide(index) {
    // Remove active class from all slides and dots
    this.slides.forEach(slide => slide.classList.remove('active'));
    this.dots.forEach(dot => dot.classList.remove('active'));

    // Add active class to current slide and dot
    if (this.slides[index]) {
      this.slides[index].classList.add('active');
    }
    if (this.dots[index]) {
      this.dots[index].classList.add('active');
    }

    this.currentSlide = index;

    // Trigger custom event
    this.container.dispatchEvent(new CustomEvent('slideChanged', {
      detail: { currentSlide: this.currentSlide }
    }));
  }

  nextSlide() {
    this.currentSlide = (this.currentSlide + 1) % this.slides.length;
    this.showSlide(this.currentSlide);
  }

  prevSlide() {
    this.currentSlide = (this.currentSlide - 1 + this.slides.length) % this.slides.length;
    this.showSlide(this.currentSlide);
  }

  goToSlide(index) {
    if (index >= 0 && index < this.slides.length) {
      this.showSlide(index);
    }
  }

  startAutoSlide() {
    if (this.slides.length <= 1) return;
    
    this.autoSlideInterval = setInterval(() => {
      this.nextSlide();
    }, 5000);
    this.isPlaying = true;
  }

  pauseAutoSlide() {
    clearInterval(this.autoSlideInterval);
    this.isPlaying = false;
  }

  resumeAutoSlide() {
    if (!this.isPlaying) {
      this.startAutoSlide();
    }
  }

  toggleAutoSlide() {
    if (this.isPlaying) {
      this.pauseAutoSlide();
    } else {
      this.startAutoSlide();
    }
  }

  isInViewport() {
    const rect = this.container.getBoundingClientRect();
    return rect.top < window.innerHeight && rect.bottom > 0;
  }

  // Public API
  getCurrentSlide() {
    return this.currentSlide;
  }

  getTotalSlides() {
    return this.slides.length;
  }

  destroy() {
    this.pauseAutoSlide();
    // Remove event listeners would go here if needed
  }
}

// Auto-initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  const heroSlider = new HeroSlider('.hero');
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = HeroSlider;
}
