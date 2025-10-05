// Utility Functions
const utils = {
  // Debounce function for performance optimization
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  },

  // Throttle function for scroll events
  throttle(func, limit) {
    let inThrottle;
    return function() {
      const args = arguments;
      const context = this;
      if (!inThrottle) {
        func.apply(context, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  },

  // Check if element is in viewport
  isInViewport(element, threshold = 0.1) {
    const rect = element.getBoundingClientRect();
    const windowHeight = window.innerHeight || document.documentElement.clientHeight;
    const windowWidth = window.innerWidth || document.documentElement.clientWidth;

    const vertInView = (rect.top <= windowHeight * (1 - threshold)) && 
                      ((rect.top + rect.height) >= windowHeight * threshold);
    const horInView = (rect.left <= windowWidth) && ((rect.left + rect.width) >= 0);

    return vertInView && horInView;
  },

  // Smooth scroll to element
  scrollToElement(element, offset = 0) {
    const elementPosition = element.getBoundingClientRect().top + window.pageYOffset;
    const offsetPosition = elementPosition - offset;

    window.scrollTo({
      top: offsetPosition,
      behavior: 'smooth'
    });
  },

  // Get element by data attribute
  getByData(attribute, value = null, parent = document) {
    if (value) {
      return parent.querySelector(`[data-${attribute}="${value}"]`);
    }
    return parent.querySelector(`[data-${attribute}]`);
  },

  // Get all elements by data attribute
  getAllByData(attribute, value = null, parent = document) {
    if (value) {
      return parent.querySelectorAll(`[data-${attribute}="${value}"]`);
    }
    return parent.querySelectorAll(`[data-${attribute}]`);
  },

  // Add event listener with automatic cleanup
  addEventListenerWithCleanup(element, event, handler, options = {}) {
    element.addEventListener(event, handler, options);
    
    // Return cleanup function
    return () => {
      element.removeEventListener(event, handler, options);
    };
  },

  // Format date for display
  formatDate(date, options = {}) {
    const defaultOptions = {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    };
    
    return new Intl.DateTimeFormat('en-US', { ...defaultOptions, ...options })
      .format(new Date(date));
  },

  // Animate number counting
  animateNumber(element, start, end, duration = 1000) {
    const startTime = performance.now();
    const range = end - start;

    function updateNumber(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      // Easing function
      const easeOut = 1 - Math.pow(1 - progress, 3);
      const current = Math.floor(start + (range * easeOut));
      
      element.textContent = current;

      if (progress < 1) {
        requestAnimationFrame(updateNumber);
      } else {
        element.textContent = end;
      }
    }

    requestAnimationFrame(updateNumber);
  },

  // Local storage helpers
  storage: {
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
      } catch (e) {
        console.warn('Failed to save to localStorage:', e);
        return false;
      }
    },

    get(key, defaultValue = null) {
      try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
      } catch (e) {
        console.warn('Failed to read from localStorage:', e);
        return defaultValue;
      }
    },

    remove(key) {
      try {
        localStorage.removeItem(key);
        return true;
      } catch (e) {
        console.warn('Failed to remove from localStorage:', e);
        return false;
      }
    }
  },

  // Cookie helpers
  cookies: {
    set(name, value, days = 7) {
      const expires = new Date();
      expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
      document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`;
    },

    get(name) {
      const nameEQ = name + "=";
      const ca = document.cookie.split(';');
      for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
      }
      return null;
    },

    delete(name) {
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
    }
  },

  // Device detection
  device: {
    isMobile() {
      return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    },

    isTablet() {
      return /iPad|Android/i.test(navigator.userAgent) && window.innerWidth >= 768;
    },

    isDesktop() {
      return !this.isMobile() && !this.isTablet();
    },

    hasTouch() {
      return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    }
  },

  // Network status
  network: {
    isOnline() {
      return navigator.onLine;
    },

    onStatusChange(callback) {
      window.addEventListener('online', () => callback(true));
      window.addEventListener('offline', () => callback(false));
    }
  },

  // Performance helpers
  performance: {
    measure(name, fn) {
      const start = performance.now();
      const result = fn();
      const end = performance.now();
      console.log(`${name} took ${end - start} milliseconds`);
      return result;
    },

    async measureAsync(name, asyncFn) {
      const start = performance.now();
      const result = await asyncFn();
      const end = performance.now();
      console.log(`${name} took ${end - start} milliseconds`);
      return result;
    }
  }
};
