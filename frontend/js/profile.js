/**
 * SciGraph Professional Researcher Profile Manager
 * User: Mandeep Kumar (mandeep6207)
 * Role: Lead Researcher & Workspace Owner
 */
const ProfileManager = {
  profile: {
    full_name: 'Mandeep Kumar',
    username: 'mandeep6207',
    display_name: 'Mandeep Kumar',
    email: 'mandeep@scigraph.ai',
    initials: 'MK',
    role: 'Lead Researcher & Workspace Owner',
    title: 'Principal AI Research Scientist',
    institution: 'SciGraph Scientific Intelligence Labs',
    department: 'Neural Knowledge Discovery & Graph AI',
    bio: 'Researching topological multimodal knowledge graphs, neural entity-relationship extraction, and low-latency grounded reasoning with generative AI.',
    research_interests: ['Multimodal RAG', 'Knowledge Graphs', 'Latent Space Synthesis', 'Diffusion Architectures', 'Attention Models'],
    skills: ['FastAPI', 'LightRAG', 'PyTorch', 'NetworkX', 'Ollama', 'Grok API'],
    avatar_url: '',
    created_at: '2026-01-01',
  },

  async init() {
    this.bindDropdown();
    this.bindEditModal();
    await this.loadProfile();
  },

  async loadProfile() {
    try {
      const data = await API.getProfile();
      if (data) {
        this.profile = { ...this.profile, ...data };
      }
    } catch (e) {
      console.warn('Could not load profile from backend, using default:', e);
    }
    this.render();
  },

  render() {
    // Top header avatar
    const headerAvatar = document.getElementById('header-avatar');
    if (headerAvatar) {
      if (this.profile.avatar_url) {
        headerAvatar.innerHTML = `<img src="${this.profile.avatar_url}" alt="Avatar" style="width:100%; height:100%; object-fit:cover; border-radius:50%;">`;
      } else {
        headerAvatar.textContent = this.profile.initials || 'MK';
      }
    }

    // Sidebar footer profile
    const sidebarAvatar = document.getElementById('sidebar-avatar');
    const sidebarName = document.getElementById('sidebar-user-name');
    const sidebarRole = document.getElementById('sidebar-user-role');
    if (sidebarAvatar) {
      if (this.profile.avatar_url) {
        sidebarAvatar.innerHTML = `<img src="${this.profile.avatar_url}" alt="Avatar" style="width:100%; height:100%; object-fit:cover; border-radius:50%;">`;
      } else {
        sidebarAvatar.textContent = this.profile.initials || 'MK';
      }
    }
    if (sidebarName) sidebarName.textContent = this.profile.display_name;
    if (sidebarRole) sidebarRole.textContent = this.profile.title || this.profile.role;

    // Dropdown header
    const dropName = document.getElementById('dropdown-user-name');
    const dropHandle = document.getElementById('dropdown-user-handle');
    if (dropName) dropName.textContent = this.profile.display_name;
    if (dropHandle) dropHandle.textContent = `@${this.profile.username}`;

    // Profile Page View
    const pageAvatar = document.getElementById('profile-page-avatar');
    const pageName = document.getElementById('profile-page-name');
    const pageTitle = document.getElementById('profile-page-title');
    const pageHandle = document.getElementById('profile-page-handle');
    const pageEmail = document.getElementById('profile-page-email');
    const pageInst = document.getElementById('profile-page-institution');
    const pageDept = document.getElementById('profile-page-department');
    const pageBio = document.getElementById('profile-page-bio');
    const pageInterests = document.getElementById('profile-page-interests-container');
    const pageSkills = document.getElementById('profile-page-skills-container');

    if (pageAvatar) {
      if (this.profile.avatar_url) {
        pageAvatar.innerHTML = `<img src="${this.profile.avatar_url}" alt="Avatar" style="width:100%; height:100%; object-fit:cover; border-radius:50%;">`;
      } else {
        pageAvatar.textContent = this.profile.initials || 'MK';
      }
    }
    if (pageName) pageName.textContent = this.profile.display_name;
    if (pageTitle) pageTitle.textContent = this.profile.title || this.profile.role;
    if (pageHandle) pageHandle.innerHTML = `@${this.profile.username} · <span id="profile-page-email">${this.profile.email || 'mandeep@scigraph.ai'}</span>`;
    if (pageInst) pageInst.textContent = this.profile.institution;
    if (pageDept) pageDept.textContent = this.profile.department;
    if (pageBio) pageBio.textContent = this.profile.bio;

    if (pageInterests && this.profile.research_interests) {
      pageInterests.innerHTML = this.profile.research_interests
        .map(i => `<span class="badge badge-emerald">${this.escapeHtml(i)}</span>`)
        .join('');
    }

    if (pageSkills && this.profile.skills) {
      pageSkills.innerHTML = this.profile.skills
        .map(s => `<span class="citation-pill">${this.escapeHtml(s)}</span>`)
        .join('');
    }
  },

  bindDropdown() {
    const trigger = document.getElementById('header-profile-btn');
    const menu = document.getElementById('profile-dropdown-menu');
    if (!trigger || !menu) return;

    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      menu.classList.toggle('show');
    });

    document.addEventListener('click', () => {
      menu.classList.remove('show');
    });

    menu.addEventListener('click', (e) => {
      e.stopPropagation();
    });
  },

  bindEditModal() {
    const editBtn = document.getElementById('btn-edit-profile');
    const modal = document.getElementById('modal-edit-profile');
    const closeBtn = document.getElementById('close-edit-profile');
    const cancelBtn = document.getElementById('cancel-edit-profile');
    const saveBtn = document.getElementById('save-edit-profile');
    const avatarInput = document.getElementById('profile-avatar-input');

    if (!modal) return;

    const openModal = () => {
      const inName = document.getElementById('input-edit-display-name');
      const inEmail = document.getElementById('input-edit-email');
      const inTitle = document.getElementById('input-edit-title');
      const inInst = document.getElementById('input-edit-institution');
      const inDept = document.getElementById('input-edit-department');
      const inBio = document.getElementById('input-edit-bio');
      const inInterests = document.getElementById('input-edit-interests');
      const inSkills = document.getElementById('input-edit-skills');

      if (inName) inName.value = this.profile.display_name || '';
      if (inEmail) inEmail.value = this.profile.email || 'mandeep@scigraph.ai';
      if (inTitle) inTitle.value = this.profile.title || '';
      if (inInst) inInst.value = this.profile.institution || '';
      if (inDept) inDept.value = this.profile.department || '';
      if (inBio) inBio.value = this.profile.bio || '';
      if (inInterests) inInterests.value = (this.profile.research_interests || []).join(', ');
      if (inSkills) inSkills.value = (this.profile.skills || []).join(', ');

      modal.classList.add('open');
    };

    const closeModal = () => {
      modal.classList.remove('open');
    };

    if (editBtn) editBtn.addEventListener('click', openModal);
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

    if (avatarInput) {
      avatarInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
          try {
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch('/profile/avatar', { method: 'POST', body: formData });
            if (!res.ok) throw new Error('Upload failed');
            const data = await res.json();
            if (data && data.avatar_url) {
              this.profile.avatar_url = data.avatar_url;
              this.render();
              Toast.show('Avatar photo updated successfully!', 'success');
            }
          } catch (err) {
            Toast.show('Failed to upload avatar: ' + err.message, 'error');
          }
        }
      });
    }

    if (saveBtn) {
      saveBtn.addEventListener('click', async () => {
        const newName = (document.getElementById('input-edit-display-name')?.value || '').trim();
        const newEmail = (document.getElementById('input-edit-email')?.value || '').trim();
        const newTitle = (document.getElementById('input-edit-title')?.value || '').trim();
        const newInst = (document.getElementById('input-edit-institution')?.value || '').trim();
        const newDept = (document.getElementById('input-edit-department')?.value || '').trim();
        const newBio = (document.getElementById('input-edit-bio')?.value || '').trim();
        const rawInterests = (document.getElementById('input-edit-interests')?.value || '').split(',').map(s => s.trim()).filter(Boolean);
        const rawSkills = (document.getElementById('input-edit-skills')?.value || '').split(',').map(s => s.trim()).filter(Boolean);

        if (!newName) {
          Toast.show('Name cannot be empty', 'error');
          return;
        }

        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';

        try {
          const updatePayload = {
            display_name: newName,
            full_name: newName,
            email: newEmail,
            title: newTitle,
            institution: newInst,
            department: newDept,
            bio: newBio,
            research_interests: rawInterests,
            skills: rawSkills,
          };

          const res = await fetch('/profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatePayload),
          });

          if (!res.ok) throw new Error('Failed to update profile');
          const data = await res.json();

          if (data && data.profile) {
            this.profile = { ...this.profile, ...data.profile };
          }
          this.render();
          closeModal();
          Toast.show('Researcher profile saved successfully!', 'success');
        } catch (err) {
          Toast.show('Failed to save profile: ' + err.message, 'error');
        } finally {
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save Profile Changes';
        }
      });
    }
  },

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
};

window.ProfileManager = ProfileManager;
