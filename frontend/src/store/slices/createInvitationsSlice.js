import { genId } from '../../lib/ids';
import { createInviteToken } from '../../lib/tokens';
import { applyRedeem, inviteError } from '../../lib/invites';
import { initialInvitations } from '../../data/invitations';

const SEVEN_DAYS = 7 * 24 * 60 * 60 * 1000;

// Invite tokens minted by the admin Add-Resident flow. redeemInvite consumes a
// token (single use) and activates the whole flat; it does NOT set currentUser —
// the caller logs the returned user in, keeping this slice free of the auth
// store. The actual valid/used/expired logic is the pure applyRedeem helper.
export const createInvitationsSlice = (set, get) => ({
  invitations: initialInvitations,

  issueInvite: ({ apartmentId, phones }) => {
    const invite = {
      id: genId('inv'),
      token: createInviteToken(),
      apartmentId,
      phones: phones || [],
      createdAt: Date.now(),
      expiresAt: Date.now() + SEVEN_DAYS,
      used: false,
    };
    set((s) => ({ invitations: [...s.invitations, invite] }));
    return invite;
  },

  findInviteByToken: (token) =>
    get().invitations.find((i) => i.token === token) || null,

  // token + optional phone (manual code path picks the member by phone).
  redeemInvite: (token, phone) => {
    const result = applyRedeem(
      { users: get().users, invitations: get().invitations },
      token,
      { phone }
    );
    if (!result.ok) {
      return { ok: false, reason: result.reason, message: inviteError[result.reason] };
    }
    set({ users: result.users, invitations: result.invitations });
    if (result.user) {
      get().showToast(`Welcome to HomeBandhu, ${result.user.name}!`, 'success');
      get().addActivity(`${result.user.name} joined ${result.user.flat}`, 'general');
    }
    return { ok: true, user: result.user };
  },
});
