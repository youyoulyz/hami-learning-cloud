// Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

import { useState, useEffect, useCallback, useMemo, memo } from 'react';
import { Table, Button, Form, InputGroup, Alert, Spinner, Modal, Badge } from 'react-bootstrap';
import AsyncSelect from 'react-select/async';
import type { MultiValue, ActionMeta, StylesConfig } from 'react-select';
import type { Group } from '@auplc/shared';

// Dark mode aware styles for react-select
const getSelectStyles = (isDark: boolean): StylesConfig<UserOption, true> => {

  return {
    menuPortal: (base) => ({ ...base, zIndex: 9999 }),
    control: (base, state) => ({
      ...base,
      minHeight: '38px',
      backgroundColor: isDark ? '#212529' : base.backgroundColor,
      borderColor: isDark ? '#495057' : base.borderColor,
      '&:hover': {
        borderColor: isDark ? '#6c757d' : base.borderColor,
      },
      ...(state.isFocused && {
        borderColor: isDark ? '#0d6efd' : '#86b7fe',
        boxShadow: isDark ? '0 0 0 0.25rem rgba(13, 110, 253, 0.25)' : '0 0 0 0.25rem rgba(13, 110, 253, 0.25)',
      }),
    }),
    menu: (base) => ({
      ...base,
      backgroundColor: isDark ? '#212529' : base.backgroundColor,
      border: isDark ? '1px solid #495057' : base.border,
    }),
    option: (base, state) => ({
      ...base,
      backgroundColor: state.isFocused
        ? (isDark ? '#495057' : '#deebff')
        : (isDark ? '#212529' : base.backgroundColor),
      color: isDark ? '#fff' : base.color,
      '&:active': {
        backgroundColor: isDark ? '#6c757d' : '#b2d4ff',
      },
    }),
    input: (base) => ({
      ...base,
      color: isDark ? '#fff' : base.color,
    }),
    placeholder: (base) => ({
      ...base,
      color: isDark ? '#adb5bd' : base.color,
    }),
    singleValue: (base) => ({
      ...base,
      color: isDark ? '#fff' : base.color,
    }),
    multiValue: (base) => ({
      ...base,
      backgroundColor: '#6c757d',
    }),
    multiValueLabel: (base) => ({
      ...base,
      color: 'white',
    }),
    multiValueRemove: (base) => ({
      ...base,
      color: 'white',
      ':hover': {
        backgroundColor: '#5a6268',
        color: 'white',
      },
    }),
    noOptionsMessage: (base) => ({
      ...base,
      color: isDark ? '#adb5bd' : base.color,
    }),
    loadingMessage: (base) => ({
      ...base,
      color: isDark ? '#adb5bd' : base.color,
    }),
  };
};
import * as api from '@auplc/shared';
import { EditGroupModal } from '../components/EditGroupModal';

interface UserOption {
  value: string;
  label: string;
}

const COLLAPSED_LIMIT = 3;

function ResourceBadges({ resources }: { resources: string[] }) {
  const [expanded, setExpanded] = useState(false);
  if (resources.length === 0) return <span className="text-muted small">--</span>;
  const visible = expanded ? resources : resources.slice(0, COLLAPSED_LIMIT);
  const hidden = resources.length - COLLAPSED_LIMIT;
  return (
    <div className="d-flex flex-wrap gap-1 align-items-center">
      {visible.map(r => <Badge key={r} bg="info" className="fw-normal">{r}</Badge>)}
      {!expanded && hidden > 0 && (
        <Badge
          bg="secondary"
          className="fw-normal"
          style={{ cursor: 'pointer' }}
          onClick={() => setExpanded(true)}
          title="Show all"
        >
          +{hidden}
        </Badge>
      )}
      {expanded && resources.length > COLLAPSED_LIMIT && (
        <Badge
          bg="secondary"
          className="fw-normal"
          style={{ cursor: 'pointer' }}
          onClick={() => setExpanded(false)}
          title="Collapse"
        >
          ▲
        </Badge>
      )}
    </div>
  );
}

// Memoized GroupRow component with inline member management
interface GroupRowProps {
  group: Group;
  onEdit: (group: Group) => void;
  onMembersChange: (groupName: string, members: string[]) => void;
  loadUserOptions: (inputValue: string, excludeUsers: string[]) => Promise<UserOption[]>;
}

const GroupRow = memo(function GroupRow({ group, onEdit, onMembersChange, loadUserOptions }: GroupRowProps) {
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDark, setIsDark] = useState(() =>
    document.documentElement.getAttribute('data-bs-theme') === 'dark'
  );

  const isGitHubTeam = group.source === 'github-team';
  const isReadOnly = group.source === 'system';

  // Watch for theme changes
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.getAttribute('data-bs-theme') === 'dark');
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-bs-theme'],
    });
    return () => observer.disconnect();
  }, []);

  // Convert current members to options
  const currentMembers: UserOption[] = group.users.map(name => ({
    value: name,
    label: name,
  }));

  // Load options excluding current members
  const loadOptions = useCallback(async (inputValue: string): Promise<UserOption[]> => {
    return loadUserOptions(inputValue, group.users);
  }, [loadUserOptions, group.users]);

  // Handle member changes
  const handleChange = useCallback(async (
    _newValue: MultiValue<UserOption>,
    actionMeta: ActionMeta<UserOption>
  ) => {
    if (isUpdating) return;

    setIsUpdating(true);
    try {
      if (actionMeta.action === 'select-option' && actionMeta.option) {
        await api.addUserToGroup(group.name, actionMeta.option.value);
        onMembersChange(group.name, [...group.users, actionMeta.option.value]);
      } else if (actionMeta.action === 'remove-value' && actionMeta.removedValue) {
        await api.removeUserFromGroup(group.name, actionMeta.removedValue.value);
        onMembersChange(group.name, group.users.filter(u => u !== actionMeta.removedValue!.value));
      } else if (actionMeta.action === 'clear') {
        for (const user of group.users) {
          await api.removeUserFromGroup(group.name, user);
        }
        onMembersChange(group.name, []);
      }
    } catch (err) {
      console.error('Failed to update group members:', err);
    } finally {
      setIsUpdating(false);
    }
  }, [group.name, group.users, onMembersChange, isUpdating]);

  return (
    <tr>
      <td style={{ width: '200px', verticalAlign: 'middle' }}>
        <div className="d-flex align-items-center gap-2">
          {group.name}
          {isGitHubTeam ? (
            <Badge bg="dark" title="Synced from GitHub Teams">
              <i className="bi bi-github me-1"></i>GitHub
            </Badge>
          ) : group.source === 'system' ? (
            <Badge bg="info" title="System-managed group">System</Badge>
          ) : (
            <Badge bg="secondary" title="Manually managed group">Manual</Badge>
          )}
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--home-text-muted)', marginTop: '2px' }}>
          {group.users.length} {group.users.length === 1 ? 'member' : 'members'}
          {(group.resources?.length ?? 0) > 0 && ` · ${group.resources!.length} resources`}
        </div>
      </td>
      <td>
        <AsyncSelect<UserOption, true>
          isMulti
          cacheOptions
          defaultOptions={false}
          value={currentMembers}
          loadOptions={loadOptions}
          onChange={handleChange}
          isDisabled={isUpdating || isReadOnly}
          isClearable={!isReadOnly}
          isLoading={isUpdating}
          placeholder={isReadOnly ? 'System-managed members' : (isGitHubTeam ? 'Add users (synced members are auto-managed)...' : 'Type to search and add users...')}
          noOptionsMessage={({ inputValue }) =>
            inputValue ? 'No users found' : 'Type to search users'
          }
          loadingMessage={() => 'Searching...'}
          menuPortalTarget={document.body}
          styles={getSelectStyles(isDark)}
          {...(isReadOnly && {
            components: { MultiValueRemove: () => null },
          })}
        />
      </td>
      <td style={{ verticalAlign: 'middle' }}>
        <ResourceBadges resources={group.resources ?? []} />
      </td>
      <td style={{ width: '120px', verticalAlign: 'middle' }}>
        <Button
          variant="outline-secondary"
          size="sm"
          onClick={() => onEdit(group)}
          title="Edit Properties"
        >
          Properties
        </Button>
      </td>
    </tr>
  );
});

export function GroupList() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [githubOrg, setGithubOrg] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<Group | null>(null);
  const [newGroupName, setNewGroupName] = useState('');
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [showInfo, setShowInfo] = useState(() =>
    localStorage.getItem('grouplist-hide-info') !== '1'
  );

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const loadGroups = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getGroups();
      setGroups(response.groups);
      setGithubOrg(response.github_org || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load groups');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGroups();
  }, [loadGroups]);

  // Memoize filtered groups to avoid recalculating on every render
  const filteredGroups = useMemo(() => {
    const searchLower = debouncedSearch.toLowerCase();
    return groups.filter(group =>
      group.name.toLowerCase().includes(searchLower)
    );
  }, [groups, debouncedSearch]);

  // Memoize edit handler
  const handleEditGroup = useCallback((group: Group) => {
    setSelectedGroup(group);
    setShowEditModal(true);
  }, []);

  // Load user options for AsyncSelect
  const loadUserOptions = useCallback(async (inputValue: string, excludeUsers: string[]): Promise<UserOption[]> => {
    if (!inputValue || inputValue.length < 1) {
      return [];
    }
    try {
      const response = await api.getUsers({ offset: 0, limit: 20, nameFilter: inputValue });
      const users = response.items || [];
      return users
        .filter(user => !excludeUsers.includes(user.name))
        .map(user => ({
          value: user.name,
          label: user.admin ? `${user.name} (Admin)` : user.name,
        }));
    } catch (err) {
      console.error('Failed to load users:', err);
      return [];
    }
  }, []);

  // Handle members change from GroupRow
  const handleMembersChange = useCallback((groupName: string, newMembers: string[]) => {
    setGroups(prev => prev.map(g =>
      g.name === groupName ? { ...g, users: newMembers } : g
    ));
  }, []);

  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) {
      setCreateError('Group name cannot be empty');
      return;
    }

    if (!/^[a-zA-Z0-9_-]+$/.test(newGroupName)) {
      setCreateError('Group name can only contain letters, numbers, hyphens, and underscores');
      return;
    }

    try {
      setCreateLoading(true);
      setCreateError(null);
      await api.createGroup(newGroupName);
      setShowCreateModal(false);
      setNewGroupName('');
      await loadGroups();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create group');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleSync = useCallback(async () => {
    try {
      setSyncing(true);
      setSyncResult(null);
      setError(null);
      const result = await api.syncGroups();
      setSyncResult(
        `Sync complete: ${result.synced} synced, ${result.failed} failed, ${result.skipped} skipped`
      );
      setTimeout(() => setSyncResult(null), 5000);
      await loadGroups();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync groups');
    } finally {
      setSyncing(false);
    }
  }, [loadGroups]);

  const handleCloseEditModal = useCallback(() => {
    setShowEditModal(false);
    setSelectedGroup(null);
  }, []);

  const handleUpdateGroup = useCallback(async () => {
    await loadGroups();
  }, [loadGroups]);

  const handleDeleteGroup = useCallback(async () => {
    await loadGroups();
  }, [loadGroups]);

  if (loading) {
    return (
      <div className="text-center py-5">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
      </div>
    );
  }

  return (
    <div>
      {/* Top Controls */}
      <div className="d-flex justify-content-between align-items-center mb-3">
        <div className="d-flex gap-2">
          <Button variant="dark" onClick={() => setShowCreateModal(true)}>
            Create Group
          </Button>
          {githubOrg && (
            <>
              <Button
                variant="outline-secondary"
                onClick={handleSync}
                disabled={syncing}
              >
                {syncing ? (
                  <><Spinner animation="border" size="sm" className="me-1" />Syncing...</>
                ) : (
                  <><i className="bi bi-arrow-repeat me-1"></i>Sync Now</>
                )}
              </Button>
              <Button
                variant="outline-secondary"
                as="a"
                href={`https://github.com/orgs/${githubOrg}/teams`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <i className="bi bi-github me-1"></i>Manage Teams
              </Button>
              {!showInfo && (
                <Button
                  variant="outline-secondary"
                  onClick={() => { setShowInfo(true); localStorage.removeItem('grouplist-hide-info'); }}
                  title="Show group info"
                >
                  <i className="bi bi-info-circle"></i>
                </Button>
              )}
            </>
          )}
        </div>
        <div className="d-flex gap-2">
<Button
            variant="outline-secondary"
            as="a"
            href={`${window.jhdata?.base_url ?? '/hub/'}admin`}
          >
            Legacy Admin
          </Button>
        </div>
      </div>

      {/* Group behavior info */}
      {githubOrg && showInfo && (
        <Alert variant="light" className="border small" dismissible onClose={() => { setShowInfo(false); localStorage.setItem('grouplist-hide-info', '1'); }}>
          <i className="bi bi-info-circle me-1"></i>
          Groups with <Badge bg="dark"><i className="bi bi-github me-1"></i>GitHub</Badge> badge are synced from{' '}
          <a href={`https://github.com/orgs/${githubOrg}/teams`} target="_blank" rel="noopener noreferrer">
            {githubOrg}
          </a>{' '}
          organization teams. Synced members are auto-managed by GitHub, but you can manually add
          users (e.g. native users) to grant them the same resources.
          Team data is captured at login, and group membership is updated when the user starts a server
          &mdash; changes on GitHub may not appear until the user re-logs in and spawns.
          Use &quot;Sync Now&quot; to immediately refresh all users&apos; team memberships.
          If a manually created group shares its name with a GitHub team, it will be automatically converted
          to a GitHub-managed group when a team member logs in and spawns. Use &quot;Release Protection&quot; in group
          properties to convert a protected group back to manual management.
        </Alert>
      )}

      {error && (
        <Alert variant="danger" dismissible onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {syncResult && (
        <Alert variant="success" dismissible onClose={() => setSyncResult(null)}>
          {syncResult}
        </Alert>
      )}

      {/* Search */}
      <div className="mb-3">
        <InputGroup style={{ maxWidth: '400px' }}>
          <InputGroup.Text><i className="bi bi-search"></i></InputGroup.Text>
          <Form.Control
            placeholder="Search groups..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <Button variant="outline-secondary" onClick={() => setSearch('')}>
              Clear
            </Button>
          )}
        </InputGroup>
      </div>

      {/* Groups Table */}
      <Table striped hover responsive>
        <thead>
          <tr>
            <th style={{ width: '200px' }}>Group Name</th>
            <th>Members</th>
            <th style={{ width: '200px' }}>Resources</th>
            <th style={{ width: '120px' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filteredGroups.map((group) => (
            <GroupRow
              key={group.name}
              group={group}
              onEdit={handleEditGroup}
              onMembersChange={handleMembersChange}
              loadUserOptions={loadUserOptions}
            />
          ))}
        </tbody>
      </Table>

      {filteredGroups.length === 0 && (
        <div className="text-center text-muted py-4">
          {debouncedSearch ? 'No groups match your search.' : 'No groups found. Create one to get started.'}
        </div>
      )}

      {/* Create Group Modal */}
      <Modal show={showCreateModal} onHide={() => setShowCreateModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Create New Group</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {createError && <Alert variant="danger">{createError}</Alert>}

          <Form.Group className="mb-3">
            <Form.Label>Group Name</Form.Label>
            <Form.Control
              type="text"
              placeholder="Enter group name"
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              disabled={createLoading}
            />
            <Form.Text className="text-muted">
              Only letters, numbers, hyphens, and underscores allowed
            </Form.Text>
          </Form.Group>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowCreateModal(false)} disabled={createLoading}>
            Cancel
          </Button>
          <Button variant="dark" onClick={handleCreateGroup} disabled={createLoading}>
            {createLoading ? 'Creating...' : 'Create Group'}
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Edit Group Modal */}
      <EditGroupModal
        show={showEditModal}
        group={selectedGroup}
        onHide={handleCloseEditModal}
        onUpdate={handleUpdateGroup}
        onDelete={handleDeleteGroup}
      />
    </div>
  );
}
