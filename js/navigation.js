// Mobile Navigation Component
class MobileNavigation {
  constructor() {
    this.mobileToggle = document.querySelector('.mobile-toggle');
    this.mobileMenu = document.querySelector('.mobile-menu');
    this.body = document.body;
    this.isOpen = false;

    if (!this.mobileToggle || !this.mobileMenu) return;

    this.init();
  }

  init() {
    this.setupEventListeners();
    this.setupDropdowns();
    this.setupResponsiveHandling();
  }

  setupEventListeners() {
    // Toggle mobile menu
    this.mobileToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggle();
    });

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
      if (this.isOpen && !this.mobileMenu.contains(e.target) && !this.mobileToggle.contains(e.target)) {
        this.close();
      }
    });

    // Close menu on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.close();
      }
    });

    // Close menu when clicking on non-dropdown links
    this.mobileMenu.querySelectorAll('.nav-link:not(.mobile-dropdown-toggle)').forEach(link => {
      link.addEventListener('click', () => {
        this.close();
      });
    });

    this.mobileMenu.querySelectorAll('.dropdown-item').forEach(item => {
      item.addEventListener('click', () => {
        this.close();
      });
    });
  }

  setupDropdowns() {
    const dropdownToggles = this.mobileMenu.querySelectorAll('.mobile-dropdown-toggle');
    
    dropdownToggles.forEach(toggle => {
      toggle.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        
        const dropdown = toggle.nextElementSibling;
        if (!dropdown) return;

        const isActive = dropdown.classList.contains('active');
        
        // Close all other dropdowns
        this.closeAllDropdowns();
        
        // Toggle current dropdown
        if (!isActive) {
          this.openDropdown(dropdown, toggle);
        }
      });
    });
  }

  setupResponsiveHandling() {
    // Handle window resize with simple debounce
    let resizeTimeout;
    const handleResize = () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        if (window.innerWidth > 768 && this.isOpen) {
          this.close();
          this.closeAllDropdowns();
        }
      }, 250);
    };

    window.addEventListener('resize', handleResize);
  }

  toggle() {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  }

  open() {
    this.mobileMenu.classList.add('active');
    this.mobileToggle.innerHTML = '<i class="fas fa-times"></i>';
    this.body.style.overflow = 'hidden';
    this.isOpen = true;

    // Focus management for accessibility
    this.mobileMenu.focus();

    // Animate menu items
    this.animateMenuItems();

    // Dispatch custom event
    this.mobileMenu.dispatchEvent(new CustomEvent('mobileMenuOpened'));
  }

  close() {
    this.mobileMenu.classList.remove('active');
    this.mobileToggle.innerHTML = '<i class="fas fa-bars"></i>';
    this.body.style.overflow = '';
    this.isOpen = false;

    // Close all dropdowns when closing menu
    this.closeAllDropdowns();

    // Dispatch custom event
    this.mobileMenu.dispatchEvent(new CustomEvent('mobileMenuClosed'));
  }

  openDropdown(dropdown, toggle) {
    dropdown.classList.add('active');
    
    // Update icon
    const icon = toggle.querySelector('i.fa-chevron-down, i.fa-chevron-up');
    if (icon) {
      icon.className = 'fas fa-chevron-up';
    }

    // Animate dropdown items
    this.animateDropdownItems(dropdown);
  }

  closeDropdown(dropdown, toggle) {
    dropdown.classList.remove('active');
    
    // Update icon
    const icon = toggle.querySelector('i.fa-chevron-down, i.fa-chevron-up');
    if (icon) {
      icon.className = 'fas fa-chevron-down';
    }
  }

  closeAllDropdowns() {
    const dropdowns = this.mobileMenu.querySelectorAll('.dropdown');
    const toggles = this.mobileMenu.querySelectorAll('.mobile-dropdown-toggle');
    
    dropdowns.forEach(dropdown => {
      dropdown.classList.remove('active');
    });

    toggles.forEach(toggle => {
      const icon = toggle.querySelector('i.fa-chevron-down, i.fa-chevron-up');
      if (icon) {
        icon.className = 'fas fa-chevron-down';
      }
    });
  }

  animateMenuItems() {
    const menuItems = this.mobileMenu.querySelectorAll('.nav-item');
    
    menuItems.forEach((item, index) => {
      item.style.opacity = '0';
      item.style.transform = 'translateX(-20px)';
      
      setTimeout(() => {
        item.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        item.style.opacity = '1';
        item.style.transform = 'translateX(0)';
      }, index * 50);
    });
  }

  animateDropdownItems(dropdown) {
    const dropdownItems = dropdown.querySelectorAll('.dropdown-item');
    
    dropdownItems.forEach((item, index) => {
      item.style.opacity = '0';
      item.style.transform = 'translateY(-10px)';
      
      setTimeout(() => {
        item.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
        item.style.opacity = '1';
        item.style.transform = 'translateY(0)';
      }, index * 30);
    });
  }

  // Public API
  isMenuOpen() {
    return this.isOpen;
  }

  forceClose() {
    this.close();
  }
}



// Global initialization function for dynamically loaded navigation
function initializeNavigation() {
  const mobileNav = new MobileNavigation();

  return mobileNav;
}

// Initialize components when DOM is loaded (for pages with static navigation)
document.addEventListener('DOMContentLoaded', () => {
  // Only initialize if navigation elements exist (for static navigation)
  if (document.querySelector('.mobile-toggle') && document.querySelector('.mobile-menu')) {
    initializeNavigation();
  }
});
