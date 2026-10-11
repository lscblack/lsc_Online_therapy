import '../api_client.dart';
import '../models/profile.dart';

class ProfileApi {
  ProfileApi(this._c);
  final ApiClient _c;

  Future<Profile> get() async => Profile.fromJson(await _c.getJson('/v1/profile'));

  Future<Profile> put(ProfileUpdate u) async =>
      Profile.fromJson(await _c.putJson('/v1/profile', body: u.toJson()));

  Future<void> wipe() => _c.delete('/v1/profile');
}
