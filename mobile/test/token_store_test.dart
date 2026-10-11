import 'package:flutter_test/flutter_test.dart';
import 'package:ubuzima/data/models/token_pair.dart';
import 'package:ubuzima/data/token_store.dart';

void main() {
  test('round-trips user token + anon id and clears', () async {
    final s = MemoryTokenStore();
    expect(await s.readUser(), isNull);
    await s.writeUser(const TokenPair(accessToken: 'a', refreshToken: 'r'));
    await s.writeAnonId('anon-1');
    expect((await s.readUser())!.accessToken, 'a');
    expect(await s.readAnonId(), 'anon-1');
    await s.clearUser();
    expect(await s.readUser(), isNull);
    expect(await s.readAnonId(), 'anon-1');
    await s.clearAnonId();
    expect(await s.readAnonId(), isNull);
  });
}
