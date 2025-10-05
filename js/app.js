// Application initialization and coordination
class App {
  constructor() {
    this.components = new Map();
    this.isInitialized = false;
    
    this.init();
  }

  init() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.initialize());
    } else {
      this.initialize();
    }
  }

  async initialize() {
    try {
      console.log('🚀 Initializing CMU Africa Research Club Website...');

      // Initialize core components
      await this.initializeComponents();
      
      // Setup global event listeners
      this.setupGlobalEventListeners();
      
      // Setup performance monitoring
      this.setupPerformanceMonitoring();
      
      // Setup error handling
      this.setupErrorHandling();

      this.isInitialized = true;
      console.log('✅ Application initialized successfully');

      // Dispatch initialization complete event
      document.dispatchEvent(new CustomEvent('appInitialized', {
        detail: { timestamp: Date.now() }
      }));

    } catch (error) {
      console.error('❌ Failed to initialize application:', error);
      this.handleInitializationError(error);
    }
  }

  async initializeComponents() {
    const startTime = performance.now();

    // Component initialization would happen here
    // For now, we'll just track that they're loaded
    
    const endTime = performance.now();
    console.log(`⚡ Components initialized in ${(endTime - startTime).toFixed(2)}ms`);
  }

  setupGlobalEventListeners() {
    // Handle page visibility changes
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.handlePageHidden();
      } else {
        this.handlePageVisible();
      }
    });

    // Handle network status changes
    window.addEventListener('online', () => {
      console.log('🌐 Network connection restored');
      this.handleNetworkStatusChange(true);
    });

    window.addEventListener('offline', () => {
      console.log('📱 Network connection lost');
      this.handleNetworkStatusChange(false);
    });

    // Handle window resize (debounced)
    let resizeTimeout;
    const debouncedResize = () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        this.handleWindowResize();
      }, 250);
    };

    window.addEventListener('resize', debouncedResize);

    // Handle unload
    window.addEventListener('beforeunload', () => {
      this.handlePageUnload();
    });
  }

  setupPerformanceMonitoring() {
    // Monitor Core Web Vitals
    if ('PerformanceObserver' in window) {
      // Largest Contentful Paint
      new PerformanceObserver((entryList) => {
        const entries = entryList.getEntries();
        const lastEntry = entries[entries.length - 1];
        console.log('📊 LCP:', lastEntry.startTime);
      }).observe({ entryTypes: ['largest-contentful-paint'] });

      // First Input Delay
      new PerformanceObserver((entryList) => {
        const entries = entryList.getEntries();
        entries.forEach(entry => {
          console.log('📊 FID:', entry.processingStart - entry.startTime);
        });
      }).observe({ entryTypes: ['first-input'] });

      // Cumulative Layout Shift
      new PerformanceObserver((entryList) => {
        const entries = entryList.getEntries();
        let cls = 0;
        entries.forEach(entry => {
          if (!entry.hadRecentInput) {
            cls += entry.value;
          }
        });
        if (cls > 0) {
          console.log('📊 CLS:', cls);
        }
      }).observe({ entryTypes: ['layout-shift'] });
    }
  }

  setupErrorHandling() {
    // Global error handler
    window.addEventListener('error', (event) => {
      console.error('❌ Global error:', event.error);
      this.handleError(event.error, 'global');
    });

    // Unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      console.error('❌ Unhandled promise rejection:', event.reason);
      this.handleError(event.reason, 'promise');
    });
  }

  // Event Handlers
  handlePageHidden() {
    console.log('👁️ Page hidden - pausing non-essential processes');
    // Pause animations, timers, etc.
    document.dispatchEvent(new CustomEvent('pagePaused'));
  }

  handlePageVisible() {
    console.log('👁️ Page visible - resuming processes');
    // Resume animations, timers, etc.
    document.dispatchEvent(new CustomEvent('pageResumed'));
  }

  handleNetworkStatusChange(isOnline) {
    document.dispatchEvent(new CustomEvent('networkStatusChanged', {
      detail: { isOnline }
    }));

    if (!isOnline) {
      this.showOfflineNotification();
    }
  }

  handleWindowResize() {
    const { innerWidth, innerHeight } = window;
    
    document.dispatchEvent(new CustomEvent('windowResized', {
      detail: { width: innerWidth, height: innerHeight }
    }));

    // Update CSS custom properties for viewport dimensions
    document.documentElement.style.setProperty('--viewport-width', `${innerWidth}px`);
    document.documentElement.style.setProperty('--viewport-height', `${innerHeight}px`);
  }

  handlePageUnload() {
    console.log('👋 Page unloading - cleaning up...');
    
    // Cleanup components
    this.components.forEach(component => {
      if (component.destroy && typeof component.destroy === 'function') {
        component.destroy();
      }
    });

    // Save any pending data
    this.savePendingData();
  }

  handleError(error, type) {
    // Log error details
    const errorInfo = {
      message: error.message || 'Unknown error',
      stack: error.stack,
      type,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href
    };

    // In a real application, you would send this to an error tracking service
    console.error('📝 Error logged:', errorInfo);

    // Show user-friendly error message for critical errors
    if (type === 'global') {
      this.showErrorNotification('Something went wrong. Please refresh the page.');
    }
  }

  handleInitializationError(error) {
    const fallbackHTML = `
      <div style="
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        text-align: center;
        padding: 20px;
        background: #f8fafc;
      ">
        <div>
          <h1 style="color: #8b1538; margin-bottom: 16px;">CMU Africa Research Club</h1>
          <p style="color: #6b7280; margin-bottom: 20px;">
            We're experiencing technical difficulties. Please refresh the page.
          </p>
          <button onclick="window.location.reload()" style="
            background: #8b1538;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
          ">
            Refresh Page
          </button>
        </div>
      </div>
    `;

    document.body.innerHTML = fallbackHTML;
  }

  // Utility Methods
  showOfflineNotification() {
    const notification = document.createElement('div');
    notification.innerHTML = `
      <div style="
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: #f59e0b;
        color: white;
        text-align: center;
        padding: 12px;
        z-index: 10000;
        font-weight: 600;
      ">
        📱 You're currently offline. Some features may not work properly.
      </div>
    `;

    document.body.appendChild(notification);

    // Remove notification when back online
    const removeNotification = () => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
      window.removeEventListener('online', removeNotification);
    };

    window.addEventListener('online', removeNotification);
  }

  showErrorNotification(message) {
    const notification = document.createElement('div');
    notification.innerHTML = `
      <div style="
        position: fixed;
        top: 20px;
        right: 20px;
        background: #ef4444;
        color: white;
        padding: 16px 20px;
        border-radius: 8px;
        z-index: 10000;
        max-width: 300px;
        font-size: 14px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      ">
        ⚠️ ${message}
      </div>
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 5000);
  }

  savePendingData() {
    // Save any form data or user preferences
    const formInputs = document.querySelectorAll('input, textarea, select');
    const formData = {};

    formInputs.forEach(input => {
      if (input.name && input.value) {
        formData[input.name] = input.value;
      }
    });

    if (Object.keys(formData).length > 0) {
      try {
        localStorage.setItem('pendingFormData', JSON.stringify(formData));
      } catch (e) {
        console.warn('Failed to save form data:', e);
      }
    }
  }

  restorePendingData() {
    try {
      const pendingDataStr = localStorage.getItem('pendingFormData');
      const pendingData = pendingDataStr ? JSON.parse(pendingDataStr) : null;
      
      if (pendingData) {
        Object.entries(pendingData).forEach(([name, value]) => {
          const input = document.querySelector(`[name="${name}"]`);
          if (input) {
            input.value = value;
          }
        });

        localStorage.removeItem('pendingFormData');
      }
    } catch (e) {
      console.warn('Failed to restore form data:', e);
    }
  }

  // Public API
  getComponent(name) {
    return this.components.get(name);
  }

  registerComponent(name, component) {
    this.components.set(name, component);
  }

  isReady() {
    return this.isInitialized;
  }

  // Development helpers
  debug() {
    if (process.env.NODE_ENV === 'development') {
      console.log('🔍 App Debug Info:', {
        isInitialized: this.isInitialized,
        components: Array.from(this.components.keys()),
        performance: {
          navigation: performance.getEntriesByType('navigation')[0],
          memory: performance.memory
        }
      });
    }
  }
}

// Initialize the application
const app = new App();
