// Intersection Observer for animations
class AnimationController {
  constructor() {
    this.observers = new Map();
    this.init();
  }

  init() {
    this.setupScrollAnimations();
    this.setupCounterAnimations();
    this.setupParallaxEffects();
  }

  setupScrollAnimations() {
    // Clean up existing observer if it exists
    if (this.observers.has('animation')) {
      this.observers.get('animation').disconnect();
    }

    const animationObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('animate');
            
            // Add staggered animation for multiple elements
            const siblings = entry.target.parentElement.children;
            const index = Array.from(siblings).indexOf(entry.target);
            entry.target.style.animationDelay = `${index * 0.1}s`;
          }
        });
      },
      {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
      }
    );

    // Observe elements for animation
    const animateElements = document.querySelectorAll(
      '.research-card, .event-card, .testimonial-card, .feature-card'
    );

    console.log(`🎯 Found ${animateElements.length} elements to animate`);

    animateElements.forEach(el => {
      animationObserver.observe(el);
    });

    this.observers.set('animation', animationObserver);
  }

  setupCounterAnimations() {
    // Clean up existing observer if it exists
    if (this.observers.has('counter')) {
      this.observers.get('counter').disconnect();
    }

    const counterObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            this.animateCounter(entry.target);
            counterObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.5 }
    );

    const counters = document.querySelectorAll('.stat-number');
    console.log(`🔢 Found ${counters.length} counters to animate`);
    
    counters.forEach(counter => {
      counterObserver.observe(counter);
    });

    this.observers.set('counter', counterObserver);
  }

  setupParallaxEffects() {
    const parallaxElements = document.querySelectorAll('[data-parallax]');
    
    if (parallaxElements.length === 0) return;

    const handleParallax = utils.throttle(() => {
      const scrolled = window.pageYOffset;
      
      parallaxElements.forEach(element => {
        const rate = scrolled * -0.5;
        element.style.transform = `translateY(${rate}px)`;
      });
    }, 16); // ~60fps

    window.addEventListener('scroll', handleParallax);
  }

  animateCounter(element) {
    const text = element.textContent;
    const number = parseInt(text.replace(/\D/g, ''));
    const suffix = text.replace(/\d/g, '');
    
    if (isNaN(number)) return;

    utils.animateNumber(element, 0, number, 2000);
    
    // Add suffix back after animation
    const originalAnimate = utils.animateNumber;
    utils.animateNumber = function(el, start, end, duration) {
      const startTime = performance.now();
      const range = end - start;

      function updateNumber(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(start + (range * easeOut));
        
        el.textContent = current + suffix;

        if (progress < 1) {
          requestAnimationFrame(updateNumber);
        } else {
          el.textContent = end + suffix;
        }
      }

      requestAnimationFrame(updateNumber);
    };

    utils.animateNumber(element, 0, number, 2000);
    utils.animateNumber = originalAnimate;
  }

  // Public API
  addScrollAnimation(selector) {
    const elements = document.querySelectorAll(selector);
    elements.forEach(el => {
      this.observers.get('animation')?.observe(el);
    });
  }

  removeScrollAnimation(selector) {
    const elements = document.querySelectorAll(selector);
    elements.forEach(el => {
      this.observers.get('animation')?.unobserve(el);
    });
  }

  destroy() {
    this.observers.forEach(observer => observer.disconnect());
    this.observers.clear();
  }
}

// Scroll Effects Controller
class ScrollEffectsController {
  constructor() {
    this.ticking = false;
    this.mainNav = document.querySelector('.main-nav');
    
    this.init();
  }

  init() {
    if (!this.mainNav) return;

    this.setupScrollListener();
    this.setupSmoothScrolling();
  }

  setupScrollListener() {
    const handleScroll = () => {
      if (!this.ticking) {
        requestAnimationFrame(() => {
          this.updateScrollEffects();
          this.ticking = false;
        });
        this.ticking = true;
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
  }

  updateScrollEffects() {
    const scrollY = window.scrollY;
    
    // Navigation background change
    if (scrollY > 100) {
      this.mainNav.style.background = 'rgba(255, 255, 255, 0.98)';
      this.mainNav.style.borderBottom = '1px solid rgba(139, 21, 56, 0.1)';
      this.mainNav.classList.add('scrolled');
    } else {
      this.mainNav.style.background = 'rgba(255, 255, 255, 0.95)';
      this.mainNav.style.borderBottom = '1px solid rgba(0, 0, 0, 0.1)';
      this.mainNav.classList.remove('scrolled');
    }

    // Dispatch scroll event for other components
    document.dispatchEvent(new CustomEvent('scrollUpdate', {
      detail: { scrollY }
    }));
  }

  setupSmoothScrolling() {
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', (e) => {
        e.preventDefault();
        
        const targetId = anchor.getAttribute('href');
        const targetElement = document.querySelector(targetId);
        
        if (targetElement) {
          const navHeight = this.mainNav.offsetHeight;
          utils.scrollToElement(targetElement, navHeight + 20);
        }
      });
    });
  }
}

// Interactive Elements Controller
class InteractiveElementsController {
  constructor() {
    this.init();
  }

  init() {
    this.setupButtonInteractions();
    this.setupCardInteractions();
    this.setupFormInteractions();
    this.setupImageLoading();
  }

  setupButtonInteractions() {
    // Register buttons
    document.querySelectorAll('.register-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        this.handleRegistration(btn);
      });
    });

    // Newsletter buttons
    document.querySelectorAll('.newsletter-buttons .btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        this.handleNewsletterAction(btn);
      });
    });

    // CTA buttons
    document.querySelectorAll('.cta-buttons .btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        this.handleCTAAction(btn);
      });
    });

    // Research links
    document.querySelectorAll('.research-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        this.handleResearchLink(link);
      });
    });

    // View all events link
    const viewAllLink = document.querySelector('.view-all-link');
    if (viewAllLink) {
      viewAllLink.addEventListener('click', (e) => {
        e.preventDefault();
        this.handleViewAllEvents();
      });
    }
  }

  setupCardInteractions() {
    // Add touch-friendly hover effects for mobile
    if (utils.device.hasTouch()) {
      document.querySelectorAll('.research-card, .event-card, .testimonial-card, .feature-card').forEach(card => {
        card.addEventListener('touchstart', function() {
          this.style.transform = 'translateY(-4px)';
        }, { passive: true });
        
        card.addEventListener('touchend', function() {
          setTimeout(() => {
            this.style.transform = '';
          }, 150);
        }, { passive: true });
      });
    }
  }

  setupFormInteractions() {
    // Form validation and enhancement would go here
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        this.handleFormSubmission(form);
      });
    });
  }

  setupImageLoading() {
    // Progressive image loading - exclude images that have their own handling
    document.querySelectorAll('img').forEach(img => {
      // Skip images in executive-image containers (they have their own CSS handling)
      if (img.closest('.executive-image') || img.closest('.faculty-image')) {
        return;
      }

      img.addEventListener('load', function() {
        this.style.opacity = '1';
      });

      // Add loading state
      img.style.opacity = '0';
      img.style.transition = 'opacity 0.3s ease';
    });
  }

  // Event handlers
  handleRegistration(button) {
    const eventTitle = button.closest('.event-card')?.querySelector('.event-title')?.textContent;
    
    this.showModal('Event Registration', `
      <p>You're registering for: <strong>${eventTitle}</strong></p>
      <p>Registration functionality would be implemented here.</p>
    `);
  }

  handleNewsletterAction(button) {
    const text = button.textContent.trim();
    
    if (text.includes('Download')) {
      this.showNotification('Newsletter download would start here.', 'success');
    } else if (text.includes('Archive')) {
      this.showNotification('Newsletter archive would open here.', 'info');
    }
  }

  handleCTAAction(button) {
    const text = button.textContent.trim();
    
    if (text.includes('Member')) {
      this.showModal('Join Our Community', `
        <p>Welcome to the CMU Africa Research Club!</p>
        <p>Membership signup would be implemented here.</p>
      `);
    } else if (text.includes('Touch')) {
      this.showModal('Get in Touch', `
        <p>Contact form would be implemented here.</p>
      `);
    }
  }

  handleResearchLink(link) {
    // Navigate to the actual project page
    const href = link.getAttribute('href');
    if (href) {
      window.location.href = href;
    }
  }

  handleViewAllEvents() {
    this.showNotification('Events page would open here.', 'info');
  }

  handleFormSubmission(form) {
    // Basic form handling
    const formData = new FormData(form);
    console.log('Form submitted:', Object.fromEntries(formData));
    
    this.showNotification('Form submitted successfully!', 'success');
  }

  // Utility methods
  showModal(title, content) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <h3>${title}</h3>
          <button class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          ${content}
        </div>
      </div>
    `;

    // Add styles
    modal.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0,0,0,0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
      opacity: 0;
      transition: opacity 0.3s ease;
    `;

    const modalContent = modal.querySelector('.modal');
    modalContent.style.cssText = `
      background: white;
      border-radius: 12px;
      max-width: 500px;
      width: 90%;
      max-height: 80vh;
      overflow-y: auto;
      transform: scale(0.9);
      transition: transform 0.3s ease;
    `;

    const modalHeader = modal.querySelector('.modal-header');
    modalHeader.style.cssText = `
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 20px;
      border-bottom: 1px solid #e5e7eb;
    `;

    const modalBody = modal.querySelector('.modal-body');
    modalBody.style.cssText = `
      padding: 20px;
    `;

    const closeButton = modal.querySelector('.modal-close');
    closeButton.style.cssText = `
      background: none;
      border: none;
      font-size: 24px;
      cursor: pointer;
      color: #6b7280;
    `;

    document.body.appendChild(modal);

    // Animate in
    setTimeout(() => {
      modal.style.opacity = '1';
      modalContent.style.transform = 'scale(1)';
    }, 10);

    // Close handlers
    const closeModal = () => {
      modal.style.opacity = '0';
      modalContent.style.transform = 'scale(0.9)';
      setTimeout(() => {
        if (modal.parentNode) {
          modal.parentNode.removeChild(modal);
        }
      }, 300);
    };

    closeButton.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeModal();
      }
    });

    document.addEventListener('keydown', function escHandler(e) {
      if (e.key === 'Escape') {
        closeModal();
        document.removeEventListener('keydown', escHandler);
      }
    });
  }

  showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;

    const colors = {
      success: '#10b981',
      error: '#ef4444',
      warning: '#f59e0b',
      info: '#3b82f6'
    };

    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 16px 20px;
      background: ${colors[type] || colors.info};
      color: white;
      border-radius: 8px;
      z-index: 10000;
      font-size: 14px;
      font-weight: 500;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      transform: translateX(100%);
      transition: transform 0.3s ease;
      max-width: 300px;
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
      notification.style.transform = 'translateX(0)';
    }, 10);

    setTimeout(() => {
      notification.style.transform = 'translateX(100%)';
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300);
    }, 3000);
  }
}

// Initialize all components when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  const animationController = new AnimationController();
  const scrollEffectsController = new ScrollEffectsController();
  const interactiveElementsController = new InteractiveElementsController();
});

// Reinitialize animations when dynamic content is loaded
document.addEventListener('contentLoaded', () => {
  console.log('🔄 Reinitializing animations after content load...');
  
  // Reinitialize the animation controller for the newly loaded content
  if (window.animationController) {
    window.animationController.setupScrollAnimations();
    window.animationController.setupCounterAnimations();
  }
});
